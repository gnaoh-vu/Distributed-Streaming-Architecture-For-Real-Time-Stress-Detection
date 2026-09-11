import numpy as np

import torch
from torch import nn
from torch import optim
from torch.utils.data import DataLoader, TensorDataset

from adarp import SignalType, Signal, PARTICIPANTS
from adarp import get_segments, extract_windows_from_signal


def prepare_data(
        include_signals_types: list[SignalType], 
        from_patient=0, to_patient=len(PARTICIPANTS)
):
    _, stress = get_segments(
        include_signals_types, 
        from_patient=from_patient, to_patient=to_patient
    )
    _, not_stress = get_segments(
        include_signals_types, is_stress=False, 
        from_patient=from_patient, to_patient=to_patient
    )

    data = { 'HR': (), 'EDA': (), 'BVP': (), 'ACC': (), 'TEMP': () }

    for s_type in include_signals_types:
        stress_signals = extract_windows_from_signal(stress[str(s_type)])
        not_stress_signals = extract_windows_from_signal(not_stress[str(s_type)])

        X_stress = torch.from_numpy(
            np.stack([s.data for s in stress_signals])
        )

        X_not_stress = torch.from_numpy(
            np.stack([s.data for s in not_stress_signals])
        )

        X = torch.cat([X_stress, X_not_stress], dim=0)
        y = torch.cat([
            torch.ones(len(X_stress), dtype=int),
            torch.zeros(len(X_not_stress), dtype=int)
        ], dim=0)

        data[str(s_type)] = (X, y)

    return data

train = prepare_data([SignalType.EDA], to_patient=9)
test = prepare_data([SignalType.EDA], from_patient=9)
 
X_eda_train, y_eda_train = train['EDA']
X_eda_test, y_eda_test = test['EDA']

training_data = TensorDataset(X_eda_train, y_eda_train)
train_loader = DataLoader(
    training_data,
    batch_size=64,
    shuffle=True,
)

class StressModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv1d(1, 100, kernel_size=5, padding='same'),
            nn.ReLU(),

            nn.Conv1d(100, 50, kernel_size=10, padding='same'),
            nn.ReLU(),

            nn.MaxPool1d(kernel_size=240),

            nn.Linear(50, 128), nn.ReLU(),
            nn.Dropout(p=0.1)

            nn.Linear(128, 256), nn.ReLU(),
            nn.Dropout(p=0.3)

            nn.Linear(256, 64),
            nn.ReLU(),

            nn.Linear(64, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.network(x)
        return x

model = StressModel()
loss = nn.CrossEntropyLoss()
optim = optim.Adam(model.parameters(), lr=0.002558)
