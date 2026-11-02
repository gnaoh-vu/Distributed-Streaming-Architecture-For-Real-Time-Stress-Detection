import argparse
import json
import math
import csv

def read_csv():
    records = {}
    with open('./cpu_ram.csv', newline='') as file:
        for row in csv.DictReader(file):
            node = row['container']
            if node not in records:
                records[node] = {'cpu_percent': [], 'memory_usage': []}

            cpu_percent = float(row['cpu_percent'][:-1])

            memory = row['memory_usage'].split(' / ')[0]
            memory_metric = memory[-3:]
            memory_usage = float(memory[:-3])
            memory_usage = memory_usage if memory_metric == 'GiB' else memory_usage / 1024

            records[node]['cpu_percent'].append(cpu_percent)
            records[node]['memory_usage'].append(memory_usage)

    return records

records = read_csv()
for container, data in records.items():
    print({
        'container': container,
        'avg_cpu_percent': sum(data['cpu_percent']) / len(data['cpu_percent']),
        'avg_memory_usage': sum(data['memory_usage']) / len(data['memory_usage'])
    })
    print(data['cpu_percent'])
    print(data['memory_usage'])
