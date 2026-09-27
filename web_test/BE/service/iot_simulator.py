#Testing IOT Simulator -> Change to  MQTT -> KAFKA Later

import asyncio
import time

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