import os
import time
import asyncio

from models import *
from web_test.BE.config import SENSOR_PATH  
from web_test.BE.service.get_raw_data import get_raw_sensor_data

async def stream_iot_data(patient_path: str):
    raw_info = get_raw_sensor_data(patient_path)
    sensor_data = raw_info["data"]
    freq = raw_info["freq"]
    delay = 1.0 / freq

    for index, value in enumerate(sensor_data):
        current_time = time.time()  

        yield {
            "timestamp": current_time,
            "value": float(value),
            "index": index
        }

        await asyncio.sleep(delay)

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
