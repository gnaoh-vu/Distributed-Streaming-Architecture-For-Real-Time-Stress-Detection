import torch
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..service.iot_simulator import stream_iot_data
from ..service.prediction import predict_realtime


from web_test.BE.config import TEST_PATIENT, WINDOW_SIZE

from web_test.BE.schemas.model import SensorSignal, RealtimePayload, PredictionResult


router = APIRouter(prefix="/ws",tags=["Realtime-IOT"])

@router.websocket("/predict")
async def predicting_realtime(websocket: WebSocket, patient_path: str = TEST_PATIENT) -> PredictionResult:
    await websocket.accept()
    buffer = []

    try:
        async for packet in stream_iot_data(patient_path):
            eda_val = packet["value"]
            sensor_time = packet["timestamp"]

            buffer.append(eda_val)
            if len(buffer) > WINDOW_SIZE:
                buffer.pop(0)

            prediction_result = predict_realtime(buffer)

            metrics_data = SensorSignal(
                timestamp = sensor_time,
                eda = eda_val,
                # hr = None,
                # acc = None,
                # bvp = None,
                # ibi = None,
                # temp = None,
            )
            

            payload = RealtimePayload(
                patient_id = patient_path,
                timestamp = time.time(), # Time of Websocket Package
                metrics = metrics_data,
                prediction = prediction_result                
            )

            await websocket.send_json(payload.model_dump())

    except WebSocketDisconnect:
        print("Disconnected")



                