from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import ValidationError

from schemas.model import PredictionResult, SensorSignal, RealtimePayload
from service.detection import predict_stress_testing

import time
import asyncio

app = FastAPI()

@app.websocket("/ws/patients/{patient_id}")
async def predict_endpoint(websocket: WebSocket, patient_id: str):
    await websocket.accept()
    print(" Patient {patient_id}")

    try:
        while True:
            data = await websocket.receive_json()

            sensor_data = SensorSignal(**data)

            prediction = predict_stress_testing(sensor_data)

            res = RealtimePayload(
                patient_id = patient_id,
                timestamp = time.time(),
                metrics = sensor_data,
                prediction = prediction
            )

            await websocket.send_json(res.model_dump())

    except WebSocketDisconnect:
        print(f"Client disconnected: {patient_id}")
    except ValidationError as e:
        print(f"Data validation error: {e}")
        await websocket.close()
    except Exception as e:
        print(f"Unexpected error: {e}")

