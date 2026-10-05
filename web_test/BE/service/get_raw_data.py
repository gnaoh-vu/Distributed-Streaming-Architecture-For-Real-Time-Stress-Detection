import os
import time

from models import *
from web_test.BE.config import SENSOR_PATH  

def get_raw_sensor_data(patient_path: str):
    path = os.path.join(SENSOR_PATH, patient_path)
    signal = read_signal_data(SignalType.EDA, path)
    timestamps = read_tag_timestamps(path) #Click Event
    
    min_max_scaler(signal)
    
    cutoff = int(3600 * 5.65 * signal.freq)
    clean_y = signal.data[cutoff:]
    
    return {
        "data": clean_y,
        "freq": signal.freq,
        "timestamps": timestamps
    }