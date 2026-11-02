import re
import csv
import time
import argparse
import subprocess

LINE = re.compile(r"^(?:CreateTime|LogAppendTime):(\d+)\t?(.*)$")

parser = argparse.ArgumentParser()
parser.add_argument('topic', choices=['signal', 'prediction'])
parser.add_argument('duration', type=int, default=600)
parser.add_argument('--output', required=True)

args = parser.parse_args()
command = [
    "docker", "compose", "exec", "kafka-1",
    "/opt/kafka/bin/kafka-console-consumer.sh",
    "--bootstrap-server", "kafka-1:9092",
    "--topic", args.topic,
    "--property", "print.timestamp=true",
    "--property", "print.key=true",
    "--property", "print.value=true",
]

proc = subprocess.Popen(
    command,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

end = time.monotonic() + args.duration
counts = {}

with open(args.output, 'w', newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["create_time", "received_host_time", "key", "value"])
    while time.monotonic() < end and proc.poll() is None:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.01)
            continue

        match = LINE.match(line.rstrip("\n"))
        if not match:
            continue

        received = int(time.time())
        create_time = int(match.group(1)) // 1_000

        rest = match.group(2)
        key, sep, value = rest.partition("\t")
        if not sep:
            key = ""
            value = rest

        writer.writerow([create_time, received, key, value])
        counts[create_time] = counts.get(create_time, 0) + 1

proc.terminate()
proc.wait(timeout=5)
print(f"Collected {sum(counts.values())} records in {args.output}")
print(f"Throughput: {sum(counts.values()) / args.duration} records/s")
