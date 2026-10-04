import os
import random
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, balanced_accuracy_score, recall_score, confusion_matrix, precision_recall_curve

from .constant import *
from .adarp import get_segments
from .features import extract_hrv_and_eda

def get_p_baselines(all_p_signals):
  all_p_baselines = {p: {} for p in all_p_signals.keys()}

  for p, p_signals in all_p_signals.items():
    if not p_signals: 
      continue

    eda_features, hrv_features = extract_hrv_and_eda(p_signals)

    all_p_baselines[p] = {
        'HRV': {'mean': np.mean(hrv_features, axis=0), 'std': np.std(hrv_features, axis=0)},
        'EDA': {'mean': np.mean(eda_features, axis=0), 'std': np.std(eda_features, axis=0)}
    }

  return all_p_baselines
  
def prepare_data(
        path:str, include_signals_types: list[SignalType],
        from_patient=None, to_patient=None, left_out=[],
        undersampling=False
):
    _, stress = get_segments(
        path, include_signals_types,
        from_patient=from_patient, to_patient=to_patient, left_out=left_out
    )

    p_not_stress, not_stress = get_segments(
        path, include_signals_types, is_stress=False,
        from_patient=from_patient, to_patient=to_patient, left_out=left_out
    )

    p_baselines = get_p_baselines(p_not_stress)
    data = { 'HR': (), 'EDA': (), 'BVP': (), 'ACC': (), 'TEMP': () }

    for s_type in include_signals_types:
        stress_hrv, stress_eda = extract_hrv_and_eda(stress, p_baselines)
        not_stress_hrv, not_stress_eda = extract_hrv_and_eda(not_stress, p_baselines)

        stress_features = np.hstack((np.array(stress_hrv), np.array(stress_eda)))
        not_stress_features = np.hstack((np.array(not_stress_hrv), np.array(not_stress_eda)))

        if undersampling:
            rng = np.random.default_rng()
            not_stress_features = rng.choice(not_stress_features, size=stress_features.shape[0], axis=0, replace=False)

        X_stress = torch.from_numpy(stress_features)
        X_not_stress = torch.from_numpy(not_stress_features)

        X = torch.cat([X_stress, X_not_stress], dim=0)
        y = torch.cat([
            torch.ones(len(X_stress), dtype=int),
            torch.zeros(len(X_not_stress), dtype=int)
        ], dim=0)

        data[str(s_type)] = (X, y)

    return data

all_y_pred = []
all_y_true = []
num_p = len(os.listdir(ADARP_SENSOR_DATA_PATH))

for p_left in range(num_p):
  print('-'*20)
  print(f"Exclude: {p_left}")

  p_tune = p_left + 1 if p_left < num_p - 1 else 0
  train_ = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA], left_out=[p_left, p_tune], undersampling=True)
  tune_ = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA], from_patient=p_tune, to_patient=p_tune)
  val_ = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA], from_patient=p_left, to_patient=p_left)

  X_train, y_train = train_['EDA']
  X_tune, y_tune = tune_['EDA']
  X_val, y_val = val_['EDA']

  X_train_np = X_train.numpy()
  y_train_np = y_train.numpy()
  X_tune_np = X_tune.numpy()
  y_tune_np = y_tune.numpy()
  X_val_np = X_val.numpy()
  y_val_np = y_val.numpy()

  print(f"Train sample: {X_train.shape}")

  rf = RandomForestClassifier(
      n_estimators=300,
      max_depth=None,
      min_samples_leaf=5,
      class_weight='balanced',
      n_jobs=-1,
      random_state=42,
  )

  rf.fit(X_train_np, y_train_np)

  probs_tune = rf.predict_proba(X_tune.numpy())[:, 1]
  precision, recall, thresholds = precision_recall_curve(y_tune.numpy(), probs_tune)

  min_recall = 0.80
  valid = recall >= min_recall
  best_idx = np.argmax(np.where(valid, precision, -1)) if valid.any() else np.argmax(recall)
  best_threshold = thresholds[best_idx] if best_idx < len(thresholds) else 0.5

  probs_val = rf.predict_proba(X_val_np)[:, 1]
  pred_y = (probs_val >= best_threshold).astype(int)

  all_y_true.append(y_val_np)
  all_y_pred.append(pred_y)

  metrics = {
      'f1': f1_score(y_val_np, pred_y, average='macro'),
      'balanced_acc': balanced_accuracy_score(y_val_np, pred_y),
      'confusion_matrix': confusion_matrix(y_val_np, pred_y),
  }

  print('Metrics:')
  print(metrics)

all_y_true = np.concatenate(all_y_true)
all_y_pred = np.concatenate(all_y_pred)

metrics = {
    'f1': f1_score(all_y_true, all_y_pred, average='macro'),
    'balanced_acc': balanced_accuracy_score(all_y_true, all_y_pred),
    'confusion_matrix': confusion_matrix(all_y_true, all_y_pred),
}

print('Metrics:')
print(metrics)
