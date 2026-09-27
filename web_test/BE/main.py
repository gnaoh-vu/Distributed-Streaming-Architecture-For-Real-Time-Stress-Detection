import uvicorn

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from web_test.BE.api.endpoins import router as rest_router
from web_test.BE.api.websocket import router as websocket_router

import time
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],    
)

app.include_router(rest_router)
app.include_router(websocket_router)

@app.get("/")
def heath_check():
    return {
        "msg": "Ok"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  
        port=3000,       
        reload=True      
    )





# @app.websocket("/ws/patients/{patient_id}")
# async def predict_endpoint(websocket: WebSocket, patient_id: str):
#     await websocket.accept()
#     print(" Patient {patient_id}")

#     try:
#         while True:
#             data = await websocket.receive_json()

#             sensor_data = SensorSignal(**data)

#             prediction = predict_stress_testing(sensor_data)

#             res = RealtimePayload(
#                 patient_id = patient_id,
#                 timestamp = sensor_data.timestamp,
#                 metrics = sensor_data,
#                 prediction = prediction
#             )

#             await websocket.send_json(res.model_dump())

#     except WebSocketDisconnect:
#         print(f"Client disconnected: {patient_id}")
#     except ValidationError as e:
#         print(f"Data validation error: {e}")
#         await websocket.close()
#     except Exception as e:
#         print(f"Unexpected error: {e}")




