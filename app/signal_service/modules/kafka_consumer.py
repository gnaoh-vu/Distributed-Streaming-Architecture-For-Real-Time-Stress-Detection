import json
from confluent_kafka import Consumer, KafkaError, KafkaException

patient_to_sensors = {}

def run_kafka_consumer(running: bool):
    config = {
        'bootstrap.servers': 'kafka-1:9092,kafka-2:9092',
        'auto.offset.reset': 'earliest',
        'group.id': 'consumer-12'
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

            if topic == 'signal':
                patient_to_sensors[patient_id]['sensors'].append(value)
                patient_to_sensors[patient_id]['sensors'] = patient_to_sensors[patient_id]['sensors'][-1000:]

            else:
                patient_to_sensors[patient_id]['predictions'].append(value)
                patient_to_sensors[patient_id]['predictions'] = patient_to_sensors[patient_id]['predictions'][-4:]

    except Exception as e:
        print(e, flush=True)

    finally:
        consumer.close()

def get_patient_snapshot(patient_id: str):
    return patient_to_sensors.get(patient_id, {'sensors': [], 'predictions': []})

def get_patients():
    patients = []

    for patient_id, buffers in patient_to_sensors.items():
        predictions = buffers['predictions']

        latest_prediction = max(
                predictions, 
                key=lambda prediction: prediction.get('end', 0)
        ) if predictions else None

        patients.append({
            'id': patient_id,
            'name': patient_id,
            'latest_prediction': latest_prediction,
        })

    return sorted(patients, key=lambda patient: patient['id'])
