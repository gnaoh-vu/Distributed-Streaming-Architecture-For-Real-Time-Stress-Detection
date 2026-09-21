import os
import random
import numpy as np

import torch
from torch import nn
from torch import optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import f1_score, balanced_accuracy_score, recall_score, roc_auc_score

from .adarp import SignalType, Signal, PARTICIPANTS
from .adarp import get_segments, extract_windows_from_signal

MODEL_SAVING_PATH = '../../baseline'

WESAD_SENSOR_DATA_PATH = '../WESAD'
ADARP_SENSOR_DATA_PATH = '../ADARP/Sensor Data'

EPOCHES = 50
BATCH_SIZE = 100
LEARNING_RATE = 0.01157

class SupervisedBalanceAdarpModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(1, 100, kernel_size=5, padding='same'),
            nn.ReLU(),

            nn.Conv1d(100, 50, kernel_size=10, padding='same'),
            nn.ReLU(),

            nn.AdaptiveMaxPool1d(1)
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

class SupervisedFullAdarpModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(1, 250, kernel_size=5, padding='same'),
            nn.ReLU(),

            nn.Conv1d(250, 100, kernel_size=5, padding='same'),
            nn.ReLU(),

            nn.AdaptiveMaxPool1d(1)
        )

        self.ffw = nn.Sequential(
            nn.Linear(100, 256), nn.ReLU(),
            nn.Dropout(p=0.1),

            nn.Linear(256, 128), nn.ReLU(),
            nn.Dropout(p=0.1),

            nn.Linear(128, 64),
            nn.ReLU(),

            nn.Linear(64, 2)
        )

    def forward(self, x):
        x = x.unsqueeze(1)
        x = self.cnn(x)
        x = x.squeeze(2)
        x = self.ffw(x)
        return x


def prepare_data(
        path:str, include_signals_types: list[SignalType], 
        from_patient=None, to_patient=None,
        undersampling=False
):
    _, stress = get_segments(
        path, include_signals_types, 
        from_patient=from_patient, to_patient=to_patient
    )
    _, not_stress = get_segments(
        path, include_signals_types, is_stress=False, 
        from_patient=from_patient, to_patient=to_patient
    )

    data = { 'HR': (), 'EDA': (), 'BVP': (), 'ACC': (), 'TEMP': () }

    for s_type in include_signals_types:
        stress_signals = extract_windows_from_signal(stress[str(s_type)])
        not_stress_signals = extract_windows_from_signal(not_stress[str(s_type)])

        if undersampling:
            not_stress_signals = random.sample(not_stress_signals, len(stress_signals))

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

def evaluate(y_logits, y):
    # prob = torch.sigmoid(y_logits).numpy()
    # pred_y = (prob >= 0.5).astype(int)
    pred_y = torch.argmax(y_logits.softmax(dim=1), dim=1).numpy()
    y = y.numpy()

    print(pred_y.shape, y.shape)

    metrics = {
        'f1': f1_score(y, pred_y, average='macro'),
        'balanced_acc': balanced_accuracy_score(y, pred_y),
        'stress_recall': recall_score(y, pred_y, pos_label=1),
        'non_stress_recall': recall_score(y, pred_y, pos_label=0),
        # 'roc_auc': roc_auc_score(y, prob)
    }

    return metrics

def validate(val_loader, model, loss_fn):
    total_samples = len(val_loader.dataset)
    all_logits = []
    all_labels = []
    total_loss = 0

    model.eval()
    with torch.no_grad():
        for batch, (X, y) in enumerate(val_loader):
            logits = model(X)
            all_logits.append(logits)
            all_labels.append(y)

            loss = loss_fn(logits, y)
            total_loss += loss.item() * len(y)

    all_logits = torch.cat(all_logits, dim=0)
    all_labels = torch.cat(all_labels, dim=0)

    avg_metrics = {
        'loss': total_loss / total_samples,
        **evaluate(all_logits, all_labels)
    }

    return avg_metrics

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
            loss = loss_fn(logits, y)

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
            avg_metrics = validate(val_loader, model, loss_fn) 
            val_loss =avg_metrics['loss']
            print(avg_metrics)

            if best_val_loss is None or val_loss < best_val_loss:
                patience_count = 0
                best_val_loss = val_loss
                torch.save(model.state_dict(), os.path.join(MODEL_SAVING_PATH, 'best_model.pt'))

            else:
                patience_count += 1
                if patience_count > patience: 
                    print('Early stop')
                    break


if __name__ == '__main__':
    train_ = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA], to_patient=0, undersampling=True)
    val_ = prepare_data(ADARP_SENSOR_DATA_PATH, [SignalType.EDA], to_patient=0, from_patient=0)

    X_eda_train, y_eda_train = train_['EDA']
    X_eda_val, y_eda_val = val_['EDA']

    training_data = TensorDataset(X_eda_train, y_eda_train)
    val_data = TensorDataset(X_eda_val, y_eda_val)

    train_loader = DataLoader(training_data, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=BATCH_SIZE)

    model = SupervisedFullAdarpModel()

    loss_fn = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    train(train_loader, model, loss_fn, optimizer, epoches=EPOCHES, patience=10, val_loader=val_loader)
