import os
import random

import joblib
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import RandomizedSearchCV, GroupKFold
from sklearn.metrics import f1_score, balanced_accuracy_score, recall_score, confusion_matrix, precision_recall_curve

from .signal import *
from .constants import *
from .adarp import get_segments
from .features import extract_hrv_and_eda

def get_p_baselines(all_p_signals):
  all_p_baselines = {p: {} for p in all_p_signals.keys()}

  for p, p_signals in all_p_signals.items():
    if not p_signals: 
      continue

    eda_features, hrv_features, _ = extract_hrv_and_eda(p_signals)

    all_p_baselines[p] = {
        'HRV': {'mean': np.mean(hrv_features, axis=0), 'std': np.std(hrv_features, axis=0)},
        'EDA': {'mean': np.mean(eda_features, axis=0), 'std': np.std(eda_features, axis=0)}
    }

  return all_p_baselines
  
def prepare_data(
        path:str, include_signals_types: list[SignalType],
        from_patient=None, to_patient=None, left_out=[],
        undersampling=False, normalizing=False
):
    _, stress = get_segments(
        path, include_signals_types,
        from_patient=from_patient, to_patient=to_patient, left_out=left_out
    )

    p_not_stress, not_stress = get_segments(
        path, include_signals_types, is_stress=False,
        from_patient=from_patient, to_patient=to_patient, left_out=left_out
    )

    p_baselines = get_p_baselines(p_not_stress) if normalizing else None
    data = { 'HR': (), 'EDA': (), 'BVP': (), 'ACC': (), 'TEMP': () }

    for s_type in include_signals_types:
        stress_hrv, stress_eda, stress_groups = extract_hrv_and_eda(stress, p_baselines)
        not_stress_hrv, not_stress_eda, not_stress_groups = extract_hrv_and_eda(not_stress, p_baselines)

        stress_features = np.hstack((np.array(stress_hrv), np.array(stress_eda)))
        not_stress_features = np.hstack((np.array(not_stress_hrv), np.array(not_stress_eda)))

        stress_groups = np.array(stress_groups)
        not_stress_groups = np.array(not_stress_groups)

        if undersampling:
            rng = np.random.default_rng()
            indices = rng.choice(len(not_stress_features), size=stress_features.shape[0], replace=False)
            not_stress_features = not_stress_features[indices]
            not_stress_groups = not_stress_groups[indices]

        groups = np.concatenate((stress_groups, not_stress_groups)) 
        X = np.concatenate((stress_features, not_stress_features))
        y = np.concatenate((np.ones(len(stress_features)), np.zeros(len(not_stress_features))))

        data[str(s_type)] = (X, y, groups)

    return data

def run_loso(model_fn): 
    all_y_pred = []
    all_y_true = []
    all_thresholds = []
    num_p = len(os.listdir(ADARP_SENSOR_DATA_PATH))

    for p_left in range(num_p):
      p_tune = p_left + 1 if p_left < num_p - 1 else 0
      train_ = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA], left_out=[p_left, p_tune], undersampling=True)
      tune_ = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA], from_patient=p_tune, to_patient=p_tune)
      val_ = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA], from_patient=p_left, to_patient=p_left)

      X_train, y_train, _ = train_['EDA']
      X_tune, y_tune, _ = tune_['EDA']
      X_val, y_val, _ = val_['EDA']

      model = model_fn()
      model.fit(X_train, y_train)

      probs_tune = model.predict_proba(X_tune)[:, 1]
      precision, recall, thresholds = precision_recall_curve(y_tune, probs_tune)

      min_recall = 0.80
      valid = recall >= min_recall
      best_idx = np.argmax(np.where(valid, precision, -1)) if valid.any() else np.argmax(recall)
      best_threshold = thresholds[best_idx] if best_idx < len(thresholds) else 0.5

      probs_val = model.predict_proba(X_val)[:, 1]
      pred_y = (probs_val >= best_threshold).astype(int)

      all_y_true.append(y_val)
      all_y_pred.append(pred_y)
      all_thresholds.append(best_threshold)

    all_y_true = np.concatenate(all_y_true)
    all_y_pred = np.concatenate(all_y_pred)

    metrics = {
        'f1': f1_score(all_y_true, all_y_pred, average='macro'),
        'recall_score': recall_score(all_y_true, all_y_pred, average='macro'),
        'balanced_acc': balanced_accuracy_score(all_y_true, all_y_pred),
        'confusion_matrix': confusion_matrix(all_y_true, all_y_pred),
    }

    return metrics, all_thresholds

full = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA])
X_full, y_full, groups_full = full['EDA']

param_dist = {
    'n_estimators': list(range(150, 601, 25)),
    'max_depth': [3, 5, 8, 12, None],
    'min_samples_leaf': list(range(2, 21)),
    'max_features': ['sqrt', 'log2', 0.5, None],
    'class_weight': ['balanced', 'balanced_subsample', None],
}

search = RandomizedSearchCV(
    estimator=RandomForestClassifier(n_jobs=-1, random_state=42),
    param_distributions=param_dist,
    n_iter=40,
    scoring='average_precision',
    cv=GroupKFold(n_splits=5),
    n_jobs=-1,
    random_state=42,
    verbose=1,
)

search.fit(X_full, y_full, groups=groups_full)
joblib.dump(search.best_estimator_, 'rf_final_model.joblib')

print("Best params:", search.best_params_)
print("Best PR-AUC:", search.best_score_)

candidates = {
    'default':    lambda: RandomForestClassifier(n_estimators=300, min_samples_leaf=5, class_weight='balanced', n_jobs=-1, random_state=42),
    'shallow':    lambda: RandomForestClassifier(n_estimators=300, max_depth=5, min_samples_leaf=10, class_weight='balanced', n_jobs=-1, random_state=42),
    'tuned':      lambda: RandomForestClassifier(**search.best_params_, n_jobs=-1, random_state=42),
}

model_fn = lambda: RandomForestClassifier(**search.best_params_, n_jobs=-1, random_state=42)
for name, model_fn in candidates.items():
    print('-'*20 + name + '-'*20)
    metrics, thresholds = run_loso(model_fn)

    print('Metrics:')
    print(metrics)

    print('Thresholds:')
    print(thresholds)
