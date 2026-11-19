import time
import json
import asyncio

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from confluent_kafka import Consumer, KafkaError, KafkaException

from modules.kafka_consumer import run_kafka_consumer, get_patient_snapshot, get_patients

running = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    global running

    consumer_task = asyncio.create_task(
        asyncio.to_thread(
            run_kafka_consumer, 
            running
        )
    )

    yield

    running = False
    await consumer_task

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],    
)

@app.websocket("/ws/patients/{patient_id}")
async def websocket_endpoint(websocket: WebSocket, patient_id: str):
    await websocket.accept()

    try:
        while True:
            await websocket.send_json(get_patient_snapshot(patient_id))
            await asyncio.sleep(0.2)

    except WebSocketDisconnect:
        return

@app.get("/patients")
def list_patients():
    return get_patients()

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"msg": 'test'}
    )

