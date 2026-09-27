import os

from models import *
from models import SignalType

from web_test.BE.config import SENSOR_PATH


def load_eda_signal(patient_path: str):
    path = os.path.join(SENSOR_PATH, patient_path)

    signal = read_signal_data(
        SignalType.EDA,
        path
    )
    timestamps = read_tag_timestamps(path)
    min_max_scaler(signal)

    y = signal.data
    x = [signal.start_time]

    for i in range(1,len(y)):
        x.append(x[i-1] + 1/signal.freq)

    y = y[int(3600*5.65*signal.freq):]
    x = x[int(3600*5.65*signal.freq):]

    return {
        'x': x, 
        'y': y.tolist(),
        'timestamps': timestamps,
    }
