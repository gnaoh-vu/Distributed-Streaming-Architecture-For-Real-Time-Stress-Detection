import json
from confluent_kafka import Consumer, KafkaError, KafkaException
from modules.db import Database

running = True

def run_kafka_consumer():
    global running

    config = {
        'bootstrap.servers': 'kafka-1:9092,kafka-2:9092',
        'auto.offset.reset': 'earliest',
        'group.id': 'trend-consumer-7'
    }

    db = Database()
    consumer = Consumer(config)
    consumer.subscribe(['prediction'])

    try:
        while running:
            msg = consumer.poll(timeout=1.0)

            if msg is None: continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF: continue
                else: raise KafkaException(msg.error())

            topic = msg.topic()
            patient_id = msg.key().decode('utf-8')
            value = json.loads(msg.value().decode('utf-8'))

            print(patient_id, value['src_ts'], flush=True)
            db.append_stress_window(patient_id, value['src_ts'])

    except Exception as e:
        print(e, flush=True)

    finally:
        consumer.close()
