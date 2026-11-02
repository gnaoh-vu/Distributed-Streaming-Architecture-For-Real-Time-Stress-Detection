import csv
import time
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('duration', type=int, default=600)
parser.add_argument('--output', required=True)

args = parser.parse_args()
end = time.monotonic() + args.duration

command = [
    "docker", "compose", "stats", "--no-stream",
    "--format", "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}"
]

with open(args.output, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp_s", "container", "cpu_percent", "memory_usage", "memory_percent"])

    while time.monotonic() < end:
        stamp = int(time.time())
        proc = subprocess.run(command, capture_output=True, text=True)
        for line in proc.stdout.splitlines():
            fields = line.split(",", 3)
            if len(fields) != 4:
                continue
            container = fields[0].lower()
            if "node-manager" in container or "spark-client" in container:
                writer.writerow([stamp, *fields])
        time.sleep(5)
