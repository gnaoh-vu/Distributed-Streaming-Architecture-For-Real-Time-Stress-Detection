import os
import numpy as np

import torch
from torch import nn
from torch import optim
from torch.utils.data import DataLoader, TensorDataset

from adarp import SignalType, Signal, PARTICIPANTS
from adarp import get_segments, extract_windows_from_signal

MODEL_SAVING_PATH = '../../baseline'
BATCH_SIZE = 147

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
val = prepare_data([SignalType.EDA], from_patient=9)
 
X_eda_train, y_eda_train = train['EDA']
X_eda_val, y_eda_val = val['EDA']

class StressModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(1, 100, kernel_size=5, padding='same'),
            nn.ReLU(),

            nn.Conv1d(100, 50, kernel_size=10, padding='same'),
            nn.ReLU(),

            nn.MaxPool1d(kernel_size=240),
        )

        self.ffw = nn.Sequential(
            nn.Linear(50, 128), nn.ReLU(),
            nn.Dropout(p=0.1),

            nn.Linear(128, 256), nn.ReLU(),
            nn.Dropout(p=0.3),

            nn.Linear(256, 64),
            nn.ReLU(),

            nn.Linear(64, 1)
        )

    def forward(self, x):
        x = x.unsqueeze(1)
        x = self.cnn(x)
        x = x.squeeze(2)
        x = self.ffw(x)
        return x

def validate(val_loader, model, loss_fn):
    total_samples = len(val_loader.dataset)
    correct_labels = 0
    total_loss = 0
    model.eval()

    with torch.no_grad():
        for batch, (X, y) in enumerate(val_loader):
            logits = model(X)
            logits = logits.squeeze(1)

            loss = loss_fn(logits, y.float())
            total_loss += loss.item() * len(X)

            correct_labels += ((logits > 0) == y).sum().item()

    avg_loss = total_loss / total_samples
    accuracy = correct_labels / total_samples

    return avg_loss, accuracy

def train(train_loader, model, loss_fn, optimizer, epoches=1, val_loader=None, patience=3):
    size = len(train_loader.dataset)
    best_val_loss = None
    patience_count = 0
    global_step = 0

    for epoch in range(epoches):
        print(f'---EPOCH[{epoch + 1}]---')
        model.train()

        for batch, (X, y) in enumerate(train_loader):
            logits = model(X)
            loss = loss_fn(logits.squeeze(1), y.float())

            global_step += 1

            loss.backward()
            optimizer.step()
            optimizer.zero_grad()

            if batch % 100 == 0:
                loss, current = loss.item(), batch * BATCH_SIZE + len(X)
                print(f"loss: {loss:>7f}  [{current:>5d}/{size:>5d}]")

            if global_step % 1000 == 0:
                torch.save(
                    model.state_dict(), 
                    os.path.join(MODEL_SAVING_PATH, f'EP{epoch}_GStep{global_step}.pt')
                )

        if val_loader:
            val_loss, accuracy = validate(val_loader, model, loss_fn) 
            print(f'val_loss: {val_loss:>7f}, accuracy: {accuracy}')

            if best_val_loss is None or val_loss < best_val_loss:
                patience_count = 0
                best_val_loss = val_loss
                torch.save(model.state_dict(), os.path.join(MODEL_SAVING_PATH, 'best_model.pt'))

            else:
                patience_count += 1
                if patience_count > patience: 
                    print('Early stop')
                    break


training_data = TensorDataset(X_eda_train, y_eda_train)
val_data = TensorDataset(X_eda_val, y_eda_val)

train_loader = DataLoader(training_data, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_data, batch_size=BATCH_SIZE)

model = StressModel()
loss_fn = nn.BCEWithLogitsLoss()
optimizer = optim.Adam(model.parameters(), lr=0.002558)

train(train_loader, model, loss_fn, optimizer, epoches=50, patience=5, val_loader=val_loader)







