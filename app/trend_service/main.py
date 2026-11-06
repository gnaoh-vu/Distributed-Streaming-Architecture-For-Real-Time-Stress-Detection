import time
import json
import asyncio

from fastapi import responses
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from confluent_kafka import Consumer, KafkaError, KafkaException

from modules.kafka_consumer import run_kafka_consumer, running
from modules.db import Database
from modules import hdfs_reader
from hdfs.util import HdfsError
from requests.exceptions import RequestException

db = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = Database()
    db.init_tables()
    hdfs_reader.connect_hdfs()
    consumer_task = asyncio.create_task(asyncio.to_thread(run_kafka_consumer))

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

@app.get("/", response_class=responses.HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"msg": 'test'}
    )

@app.get("/patients")
async def list_patients():
    return responses.JSONResponse(content=db.get_patient_ids())

@app.get("/psychologist", response_class=responses.HTMLResponse)
def psychologist_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="psychologist.html",
        context={}
    )

@app.get('/specialist-analysis/{analysis}')
async def get_specialist_analysis(analysis: hdfs_reader.Analysis, patient_id: str | None = None):
    try:
        data = hdfs_reader.read_analysis_csv(analysis)
    except (HdfsError, RequestException, OSError) as error:
        raise HTTPException(
            status_code=503,
            detail=f"Analysis data is unavailable: {error}"
        ) from error
    if patient_id is not None:
        data = [
            row for row in data
            if str(row.get("patient_id")).strip() == patient_id
        ]
    return responses.JSONResponse(
        content=jsonable_encoder(data)
    )

@app.get("/analysis/stress-histogram")
async def get_historam_data(patient_id: str):
    data = db.get_avg_stress_count_per_day_of_week(patient_id)
    return responses.JSONResponse(
        content=jsonable_encoder(data)
    )

@app.get("/analysis/stress-heatmap")
async def get_heatmap_data(patient_id: str):
    data = db.get_stress_distribution_per_day_of_week(patient_id)
    return responses.JSONResponse(
        content=jsonable_encoder(data)
    )
