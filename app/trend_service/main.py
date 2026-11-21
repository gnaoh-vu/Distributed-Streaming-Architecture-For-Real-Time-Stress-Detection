import time
import json
import asyncio
from uuid import uuid4

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
analysis_jobs = {}
active_analysis_job_id = None
analysis_job_tasks = set()

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

@app.post('/run-analyses', status_code=202)
async def run_analyses():
    global active_analysis_job_id

    if active_analysis_job_id is not None:
        active_job = analysis_jobs.get(active_analysis_job_id)
        if active_job and active_job["status"] in {"queued", "running"}:
            raise HTTPException(
                status_code=409,
                detail="An analysis batch is already running."
            )

    job_id = uuid4().hex
    analysis_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "current_analysis": None,
        "analyses": {},
        "started_at": None,
        "completed_at": None,
        "error": None,
    }
    active_analysis_job_id = job_id
    task = asyncio.create_task(run_analysis_batch(job_id))
    analysis_job_tasks.add(task)
    task.add_done_callback(analysis_job_tasks.discard)
    return {"job_id": job_id, "status": "queued"}

@app.get("/run-analyses/active")
async def get_active_analysis_job():
    if active_analysis_job_id is None:
        raise HTTPException(status_code=404, detail="No analysis batch is running.")
    return analysis_jobs[active_analysis_job_id]

@app.get("/run-analyses/{job_id}")
async def get_analysis_job(job_id: str):
    job = analysis_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis batch not found.")
    return job

async def run_analysis_batch(job_id: str):
    global active_analysis_job_id
    job = analysis_jobs[job_id]
    job["status"] = "running"
    job["started_at"] = time.time()

    try:
        for analysis in hdfs_reader.Analysis:
            job["current_analysis"] = analysis.value
            job["analyses"][analysis.value] = "running"
            try:
                succeeded = await run_job(analysis)
            except Exception:
                logger.exception("Analysis job %s raised an unexpected error.", analysis.value)
                succeeded = False

            job["analyses"][analysis.value] = "completed" if succeeded else "failed"

        failures = [
            name for name, status in job["analyses"].items()
            if status == "failed"
        ]
        
        if failures:
            job["status"] = "failed"
            job["error"] = f"Failed analyses: {', '.join(failures)}"
        else:
            job["status"] = "completed"

    except Exception as error:
        logger.exception("Analysis batch %s failed unexpectedly.", job_id)
        job["status"] = "failed"
        job["error"] = str(error)

    finally:
        job["current_analysis"] = None
        job["completed_at"] = time.time()
        if active_analysis_job_id == job_id:
            active_analysis_job_id = None

async def run_job(analysis: hdfs_reader.Analysis):
    try:
        process = await asyncio.create_subprocess_exec(
            'spark-submit',
            '--master', 'yarn',
            '--deploy-mode', 'cluster',
            '--conf', 'spark.pyspark.python=./environment/bin/python',
            '--conf', 'spark.pyspark.driver.python=./environment/bin/python',
            '--archives', 'hdfs:///shared/venv3.11.tar.gz#environment',
            '--num-executors', '2',
            '--executor-cores', '1',
            '--executor-memory', '1G',
            f'/app/spark-jobs/{analysis.value}_analysis.py',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error("Spark job %s failed.", analysis.value)
            logger.error("stdout:\n%s", stdout.decode(errors="replace"))
            logger.error("stderr:\n%s", stderr.decode(errors="replace"))

            return False

        logger.info("Spark job %s completed successfully.", analysis.value)
        return True

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
