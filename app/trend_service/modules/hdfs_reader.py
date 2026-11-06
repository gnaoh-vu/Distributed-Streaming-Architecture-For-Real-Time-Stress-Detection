import io
import csv
import pandas as pd
from enum import Enum
from hdfs import InsecureClient

client = None 

class Analysis(Enum):
    RECOVERY_SPEED = 'recovery_speed'
    STRESS_LOAD = 'stress_load'
    ANS = 'ans'

def connect_hdfs():
    global client
    client = InsecureClient('http://namenode:9870', user='hdfs')

def read_analysis_csv(type: Analysis):
    global client
    results = []

    try:
        dfs = []
        partsDir = f'/analyses/{type.value}.csv'

        contents = client.list(partsDir)
        part_files = [file for file in contents if file.startswith('part-') and file.endswith('.csv')]

        for file in part_files:
            with client.read(f'{partsDir}/{file}') as reader:
                dfs.append(pd.read_csv(reader))

        full_df = pd.concat(dfs, ignore_index=True)
        results = full_df.to_dict(orient="records")

        return results

    except pd.errors.EmptyDataError as e:
        return results

