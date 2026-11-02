import argparse
import json
import math
import csv


def percentile(values, percent):
    if len(values) == 0: return -1

    ordered = sorted(values)
    rank = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return ordered[rank]


def summarize(values):
    return {
        "count": len(values),
        "mean_s": round(sum(values) / len(values), 2) if values else None,
        "p50_s": percentile(values, 50),
        "p95_s": percentile(values, 95),
        "p99_s": percentile(values, 99),
        "maximum_s": max(values) if values else None,
    }


def read_csv(path):
    records = {}
    with open(path, newline='') as file:
        for row in csv.DictReader(file):
            try:
                payload = json.loads(row['value'])
            except (json.JSONDecodeError, KeyError):
                continue

            source_ts = payload.get('src_ts')
            if source_ts is None:
                continue

            records[float(source_ts)] = {
                'create_time': int(row['create_time']),
                'payload': payload
            }
    return records


parser = argparse.ArgumentParser()
parser.add_argument('signal_csv')
parser.add_argument('prediction_csv')
parser.add_argument('--output', default='latency.json')
args = parser.parse_args()


signals = read_csv(args.signal_csv)
predictions = read_csv(args.prediction_csv)

print(f"Signal rows with src_ts: {len(signals)}")
print(f"Prediction rows with src_ts: {len(predictions)}")
if not signals:
    print("WARNING: no signal payload has src_ts; check IoT process/image and recreate signal-topic data.")
if predictions:
    print("Prediction payloads contain latency fields.")
elif read_csv(args.prediction_csv):
    print("Unexpected prediction payload found with src_ts.")
else:
    print("WARNING: prediction topic contains no latency fields; it is likely raw-data traffic or another Spark build.")

e2e_list, src_to_kafka_list, kafka_to_spark_list, spark_to_kafka_list = [], [], [], []

for source_ts, prediction in predictions.items():
    try:
        spark_ts = float(prediction['payload']['spark_ts'])
    except (KeyError, TypeError, ValueError):
        continue

    signal = signals.get(source_ts)
    if signal is None:
        continue

    prediction_create_time = prediction['create_time']
    signal_create_time = signal['create_time']

    e2e_list.append(prediction_create_time - source_ts)
    src_to_kafka_list.append(signal_create_time - source_ts)
    kafka_to_spark_list.append(spark_ts - signal_create_time)
    spark_to_kafka_list.append(prediction_create_time - spark_ts)

result = {
    "source_to_kafka": summarize(src_to_kafka_list),
    "kafka_to_spark": summarize(kafka_to_spark_list),
    "spark_to_prediction": summarize(spark_to_kafka_list),
    "end_to_end": summarize(e2e_list),
}

print(f"Matched source/prediction pairs: {len(e2e_list)}")
with open(args.output, "w") as output:
    json.dump(result, output, indent=2)
