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

from routers import spark

running = True
patient_to_sensors = {}
patient_versions = {}
patient_updates = {}

def run_kafka_consumer():
    global running
    config = {
        'bootstrap.servers': 'kafka-1:9092,kafka-2:9092',
        'auto.offset.reset': 'earliest',
        'group.id': 'consumer-10'
    }

    consumer = Consumer(config)
    consumer.subscribe(['signal', 'prediction'])

    try:
        while running:
            msg = consumer.poll(timeout=1.0)

            if msg is None: continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF: continue
                else: raise KafkaException(msg.error())

            topic = msg.topic()
            value = json.loads(msg.value().decode('utf-8'))
            patient_id = value.get('patient_id') if topic == 'signal' else msg.key().decode('utf-8')

            if patient_id not in patient_to_sensors:
                patient_to_sensors[patient_id] = {'sensors': [], 'predictions': []}
                patient_versions[patient_id] = 0
                patient_updates[patient_id] = []

            if topic == 'signal':
                patient_to_sensors[patient_id]['sensors'].append(value)
                patient_to_sensors[patient_id]['sensors'] = patient_to_sensors[patient_id]['sensors'][-1000:]

            else:
                patient_to_sensors[patient_id]['predictions'].append(value)
                patient_to_sensors[patient_id]['predictions'] = patient_to_sensors[patient_id]['predictions'][-4:]
            
            patient_versions[patient_id] += 1
            patient_updates[patient_id].append({
                'version': patient_versions[patient_id],
                'topic': topic,
                'value': value,
            })
            patient_updates[patient_id] = patient_updates[patient_id][-1004:]

    except Exception as e:
        print(e, flush=True)

    finally:
        consumer.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global running
    running = True
    consumer_task = asyncio.create_task(asyncio.to_thread(run_kafka_consumer))

    yield

    running = False
    await consumer_task

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(spark.router)

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
    last_version = -1

    try:
        while True:
            version = patient_versions.get(patient_id, 0)
            
            if version != last_version:
                buffers = patient_to_sensors.get(
                    patient_id, {'sensors': [], 'predictions': []}
                )

                if last_version < 0:
                    snapshot = buffers
                else:
                    updates = [
                        update for update in patient_updates.get(patient_id, [])
                        if update['version'] > last_version
                    ]
                    
                    if updates and updates[0]['version'] == last_version + 1:
                        snapshot = {'sensors': [], 'predictions': []}
                        for update in updates:
                            topic_key = 'sensors' if update['topic'] == 'signal' else 'predictions'
                            snapshot[topic_key].append(update['value'])
                    else:
                        snapshot = buffers

                await websocket.send_json(snapshot)
                last_version = version

            await asyncio.sleep(0.2)

    except WebSocketDisconnect:
        return

@app.get("/patients")
def list_patients():
    patients = []
    for patient_id, buffers in patient_to_sensors.items():
        predictions = buffers['predictions']
        latest_prediction = max(predictions, key=lambda prediction: prediction.get('end', 0)) if predictions else None
        patients.append({
            'id': patient_id,
            'name': patient_id,
            'latest_prediction': latest_prediction,
        })
    return sorted(patients, key=lambda patient: patient['id'])

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"msg": 'test'}
    )

