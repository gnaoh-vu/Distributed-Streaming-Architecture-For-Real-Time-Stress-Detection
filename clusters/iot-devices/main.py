import csv
import time
import logging
import json
import os

import paho.mqtt.client as mqtt

from pathlib import Path
from itertools import chain
from typing import Iterator

MQTT_HOST = os.getenv("MQTT_HOST","emqx-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT","1883"))
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID","iot-device-1")


DATA_DIR = Path("/data")
CONTROL_DIR = Path("/control")
NEXT_FILE = CONTROL_DIR / "next"

print(os.listdir('/data'))

SIMULATION_SPEED = 1.0
METRICS = ("EDA", "IBI")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("iot-simulator")

def create_mqtt_client():

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=MQTT_CLIENT_ID
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish
    client.on_pre_connect = on_connect_fail

    client.connect(
        host=MQTT_HOST,
        port=MQTT_PORT,
        keepalive=60
    )
    client.loop_start()

    return client

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logger.info("Connected to EMQX")
    else:
        broker_msg = getattr(properties, "ReasonString", "N/A") if properties else "N/A"
        logger.error(
            "Connection failed: %s (code=%s, broker_msg='%s')",
            reason_code,
            reason_code.value,
            broker_msg,
        )

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    if reason_code == 0:
        logger.info("MQTT disconnected normally")
    else:
        broker_msg = getattr(properties, "ReasonString", "N/A") if properties else "N/A"
        logger.warning(
            "MQTT disconnected unexpectedly: %s (code=%s)",
            reason_code,
            reason_code.value,
        )

def on_publish(client, userdata, mid, reason_code, properties=None):
    if reason_code == 0 or reason_code.value == 0:
        logger.info("Publish acknowledged, batch number: mid=%s", mid)
    else:
        logger.error(
            "Publish failed: mid=%s, reason=%s (code=%s)",
            mid,
            reason_code,
            reason_code.value,
        )

def on_connect_fail(client, userdata):
    logger.error("MQTT socket/network layer connection failed (broker unreachable)")


def publish_batch(mqtt_client, record_dir, second, batch):
    topic = f"sensors/{MQTT_CLIENT_ID}"
    payload = {
        "patient_id": MQTT_CLIENT_ID,
        "record_id": record_dir.name,
        "timestamp": second,
        "eda": batch["EDA"],
        "ibi": batch["IBI"],
    }

    logger.info(json.dumps(payload))

    mqtt_client.publish(
        topic,
        json.dumps(payload),
        qos=1,
    )

def find_records() -> list[Path]:
    if not DATA_DIR.is_dir():
        raise FileNotFoundError("Not found {DATA_DIR}")

    records = (p for p in DATA_DIR.iterdir() if p.is_dir())
    records = sorted( records, key= lambda x: x.name.split('_')[1])

    if not records:
        raise RuntimeError("No records {DATA_DIR}")

    return records

def read_eda(path: Path) -> Iterator[tuple[float,str,float]]:
    with path.open("r",newline="",encoding='utf-8') as file:
        reader = csv.reader(file)

        def numeric_values():
            for row in reader:
                for cell in row:
                    cell = cell.strip()
                    if cell:
                        yield float(cell)

        values = numeric_values()

        try:
            start_timestamp_dataset = next(values)
            frequency = next(values)
            relative_timestamp = time.time()

        except StopIteration:
            raise ValueError("Missing Data")

        logger.info(
            "EDA Loaded for IOT Simulator: start=%s",
            relative_timestamp,
        )

        for index, value in enumerate(values):
            relative_time = index / frequency
            yield relative_time, "EDA", value

def read_ibi(path: Path) -> Iterator[tuple[float,str,float]]:
    with path.open("r",newline="",encoding='utf-8') as file:
        reader = csv.reader(file)

        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"IBI file is empty: {path}")

        start_timestamp_data = float(header[0].strip())
        relative_timestamp = time.time()

        logger.info(
            "IBI Loaded for IOT Simulator: start=%s",
            relative_timestamp
        )

        for line, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue

            if len(row) < 2:
                logger.warning(
                    "Missing IBI Data"
                )
                continue

            try:
                relative_time = float(row[0].strip())
                ibi_vals = float(row[1].strip())

            except ValueError:
                logger.warning(
                    "Skipping invalid IBI row %s in %s",
                    line,
                    path.name,
                )
                continue

            yield relative_time, "IBI", relative_time

def stream_data(streams: list[Iterator[tuple[float,str,float]]],) -> Iterator[tuple[float,str,float]]:
        iterators = [iter(stream) for stream in streams]
        heads = []

        for index, iterator in enumerate(iterators):
            try:
                event = next(iterator)
                heads.append((event,index))
            except StopIteration:
                pass

        while heads:
            min_pos = min(range(len(heads)),key= lambda pos: heads[pos][0][0])  

            event, stream_idx = heads.pop(min_pos)
            yield event

            try:
                next_event = next(iterators[stream_idx])
                heads.append((next_event,stream_idx))
            except StopIteration:
                pass

def build_stream(record_dir: Path) -> list[Iterator[tuple[float,str,float]]]:
    streams = []

    for sensor in METRICS:
        sensor_file = record_dir / f"{sensor}.csv"

        if not sensor_file.is_file():
            logger.warning(
                "%s missing data",
                record_dir.name
            )
            continue

        if sensor == "EDA":
            streams.append(read_eda(sensor_file))
        elif sensor == "IBI":
            streams.append(read_ibi(sensor_file))

    if not streams:
        raise RuntimeError(f"No sensor files in {record_dir}")

    return streams

def run_simulation(record_dir: Path, mqtt_client):
    logger.info("=" * 60)
    logger.info("Starting Device: %s", record_dir.name)
    logger.info("Simulation Speed: %s", SIMULATION_SPEED)

    streams = build_stream(record_dir);
    events = stream_data(streams)

    start_time = time.monotonic()
    first_time_event = None
    event_count = 0

    batch = {"EDA": [], "IBI": []}
    cur_second = None

    for relative_time, sensor, values in events:
        if first_time_event is None:
            first_time_event = relative_time

        elapsed_simulation = relative_time - first_time_event
        target_elapsed = elapsed_simulation / SIMULATION_SPEED

        actual_passing_time = time.monotonic() - start_time
        sleep_time = target_elapsed - actual_passing_time

        if sleep_time > 0:
            time.sleep(sleep_time)

        second = int(relative_time)

        if cur_second is None:
            cur_second = second

        elif cur_second != second:
            publish_batch(
                mqtt_client=mqtt_client,
                record_dir= record_dir,
                second= cur_second,
                batch=batch,
            )

            logger.info(
                "Record Device=%s | t=%d | Batch Value=%s",
                record_dir.name,
                cur_second,
                json.dumps(batch,indent=2)        
            )
            event_count += 1

            cur_second = second
            batch = {"EDA": [], "IBI": []}

        batch[sensor].append(values)

    if cur_second is not None:
        logger.info(
            "Record Device=%s | t=%d | Batch Values:\n%s",
            record_dir.name,
            cur_second,
            json.dumps(batch, indent=2),
        )

    publish_batch(
        mqtt_client=mqtt_client,
        record_dir=record_dir,
        second=cur_second,
        batch=batch,
    )

    logger.info(
    "Finished Record: %s | events =%d",
        record_dir.name,
        event_count,
    )

def wait_next() -> None:
    logger.info(
        "Waiting for Command"
    )

    while not NEXT_FILE.exists():
        time.sleep(1);

    NEXT_FILE.unlink()
    logger.info("Command Received")

def main() -> None:
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)

    records = find_records()
    logger.info("Discovered %d record(s)", len(records))
    mqtt_client = create_mqtt_client()
    try:
        for index, record_dir in enumerate(records):

            logger.info(
                "Starting record %d/%d: %s",
                index + 1,
                len(records),
                record_dir.name,
            )

            run_simulation(record_dir, mqtt_client)

            logger.info("Completed record: %s", record_dir.name)

            if index < len(records) - 1:
                wait_next()
    finally:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
        logger.info("All records completed. Simulator is exiting.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
    except Exception:
        logger.exception("Simulator failed")
        raise
