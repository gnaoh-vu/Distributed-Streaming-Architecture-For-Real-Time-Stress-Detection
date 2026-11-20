import time
import json
import asyncio
import subprocess

from fastapi import responses
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

import logging
from hdfs.util import HdfsError
from contextlib import asynccontextmanager
from requests.exceptions import RequestException

from modules.kafka_consumer import run_kafka_consumer, running
from modules.db import Database
from modules import hdfs_reader

db = None
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = Database()
    db.init_tables()
    hdfs_reader.connect_hdfs()
    # consumer_task = asyncio.create_task(asyncio.to_thread(run_kafka_consumer))

    yield

    running = False

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],    
)

@app.get("/patients")
async def list_patients():
    return responses.JSONResponse(content=db.get_patient_ids())

@app.get('/run-analyses')
async def run_analyses():
    success_jobs = []
    for analysis in hdfs_reader.Analysis:
        success = run_job(analysis)
        if (success): success_jobs.append(analysis.value)

    return { 'success_jobs': success_jobs }

def run_job(analysis: hdfs_reader.Analysis):
    try:
        result = subprocess.run([
            'spark-submit',
            '--master', 'yarn',
            '--deploy-mode', 'cluster',
            '--conf', 'spark.pyspark.python=./environment/bin/python',
            '--conf', 'spark.pyspark.driver.python=./environment/bin/python',
            '--archives', 'hdfs:///shared/venv3.11.tar.gz#environment',
            '--num-executors', '2',
            '--executor-cores', '1',
            '--executor-memory', '1G',
            f'/app/spark-jobs/{analysis.value}_analysis.py'
        ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error("Spark job failed!")
            logger.error("stdout:\n%s", result.stdout)
            logger.error("stderr:\n%s", result.stderr)

            return False

        logger.info("Spark job completed successfully.")
        return True

    except subprocess.TimeoutExpired:
        logger.exception("Spark submission timed out.")
        return False

    except FileNotFoundError:
        logger.exception("spark-submit executable not found.")
        return False

    except OSError:
        logger.exception("Failed to execute spark-submit.")
        return False

@app.get('/specialist-analysis/{analysis}')
async def get_specialist_analysis(analysis: hdfs_reader.Analysis, patient_id: str | None = None):
    try:
        data = hdfs_reader.read_analysis_csv(analysis)
        print(data)
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

        print(data)
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
