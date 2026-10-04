import os
import random
import numpy as np

import torch
from torch import nn
from torch import optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import f1_score, balanced_accuracy_score, recall_score, roc_auc_score

from .constant import *
from .adarp import get_segments
from .features import extract_hrv_and_eda

def prepare_data(
        path:str, include_signals_types: list[SignalType],
        from_patient=None, to_patient=None, left_out=[],
        undersampling=False
):
    _, stress = get_segments(
        path, include_signals_types,
        from_patient=from_patient, to_patient=to_patient, left_out=left_out
    )
    _, not_stress = get_segments(
        path, include_signals_types, is_stress=False,
        from_patient=from_patient, to_patient=to_patient, left_out=left_out
    )

    data = { 'HR': (), 'EDA': (), 'BVP': (), 'ACC': (), 'TEMP': () }

    for s_type in include_signals_types:
        stress_hrv, stress_eda = extract_hrv_and_eda(stress)
        not_stress_hrv, not_stress_eda = extract_hrv_and_eda(not_stress)

        print(f"Stress: {len(stress_hrv)}")
        print(f"Not stress: {len(not_stress_hrv)}")

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
