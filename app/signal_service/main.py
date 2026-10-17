import time
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from confluent_kafka import Consumer, KafkaError, KafkaException

from routers import spark

running = True

def run_kafka_consumer():
    config = {
        'bootstrap.servers': 'kafka-1:9092,kafka-2:9092',
        'auto.offset.reset': 'earliest',
        'group.id': 'consumer'
    }

    consumer = Consumer(config)
    consumer.subscribe(['signal'])

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None: continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF: continue
                else: raise KafkaException(msg.error())

            key = msg.key().decode('utf-8') if msg.key() else None
            value = msg.value().decode('utf-8') if msg.value() else None


    except Exception as e:
        print(e, flush=True)

    finally:
        consumer.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    running = True
    consumer_task = asyncio.to_thread(run_kafka_consumer)

    yield

    running = False
    await consumer_task


app = FastAPI(lifespan=lifespan)
app.include_router(spark.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],    
)

@app.get("/")
def heath_check():
    return {
        "msg": "Ok"
    }

