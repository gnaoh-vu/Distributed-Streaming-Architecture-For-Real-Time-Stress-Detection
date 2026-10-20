import time
import joblib

import requests
import numpy as np
import pandas as pd

import pyspark
from pyspark.sql import *
from pyspark.sql.types import *
from pyspark.sql import functions as F
from pyspark.sql.streaming.state import GroupStateTimeout

from modules import extract_hrv_and_eda_features_from_eda_one_window, extract_ibi, extract_eda
from modules import WINDOW_LENGTH, OVERLAP_RATIO
from modules import signal

spark = SparkSession.builder \
    .master("yarn") \
    .config('spark.ui.port', 4040) \
    .getOrCreate()

sc = spark.sparkContext
sc.addFile('hdfs:///shared/rf_final_model.joblib')

model_path = pyspark.SparkFiles.get('rf_final_model.joblib')
model = joblib.load(model_path)

def aggregateWindow(key, pdf_iter, state):
    id = key[0]

    if state.exists:
        current_state = state.get
        eda_buf = list(current_state[0])
        ibi_buf = list(current_state[1])
        ts_buf = list(current_state[2])
        mark = float(current_state[3])

    else:
        eda_buf, ibi_buf, ts_buf = [], [], []
        mark = None

    messages = []

    for pdf in pdf_iter:
        for _, row in pdf.iterrows():
            eda_buf.append([float(x) for x in row['eda']])
            ibi_buf.append([float(x) for x in row['ibi']])
            ts_buf.append(float(row['timestamp']))

            if mark is None: 
                mark = float(row['timestamp'])

            if (row['timestamp'] - mark + 1 >= WINDOW_LENGTH):
                start = mark
                end = start + WINDOW_LENGTH - 1

                msg = {
                    'label': int(-1),
                    'start': float(start),
                    'end': float(end),
                    'id': str(id),
                }

                w_eda, eda_rbound = extract_eda(eda_buf, ts_buf, start, end)
                w_ibi, ibi_rbound = extract_ibi(ibi_buf, ts_buf, start, end)
                eda_rbound = int(eda_rbound)
                ibi_rbound = int(ibi_rbound)

                window = signal.Window(
                    start_time=mark,
                    freq=4,
                    data=w_eda,
                    s_type=signal.SignalType.EDA,
                    segment=None
                )

                result = extract_hrv_and_eda_features_from_eda_one_window(
                    window, 
                    w_ibi
                )


                if result is not None:
                    hrv_features, eda_features = result
                    X = np.concatenate((np.array(hrv_features), np.array(eda_features))).reshape(1, -1)
                    y = model.predict(X)
                    msg['label'] = int(y[0])

                ibi_buf = ibi_buf[ibi_rbound:]
                eda_buf = eda_buf[eda_rbound:]
                ts_buf = ts_buf[eda_rbound:]
                mark += WINDOW_LENGTH

                messages.append(msg)


    if mark is not None:
        state.update((eda_buf, ibi_buf, ts_buf, mark))

    out = pd.DataFrame(messages, columns=['label', 'start', 'end', 'id'])
    out = out.astype({'label': 'int32', 'start': 'float64', 'end': 'float64', 'id': 'str'})
    yield out

def send_prediction(partition):
    session = requests.Session()

    try:
        for label, start, end, id  in partition:
            body = {'label': label, 'start': start, 'end': end, 'id': id}
            session.post(
                'http://signal-service:8000/window',
                json=body
            )

    except Exception as e:
        print(str(e), flush=True)

    finally:
        session.close()

def send_predictions(batch_df, batch_id):
    if batch_df.isEmpty(): return
    batch_df.rdd.foreachPartition(send_prediction)

signal_schema = StructType([
    StructField("device_id", StringType(), True),
    StructField("eda", ArrayType(DoubleType()), True),
    StructField("ibi", ArrayType(DoubleType()), True),
    StructField("timestamp", DoubleType(), True),
])

state_schema = StructType([
    StructField("eda", ArrayType(ArrayType(DoubleType())), True),
    StructField("ibi", ArrayType(ArrayType(DoubleType())), True),
    StructField("timestamp", ArrayType(DoubleType()), True),
    StructField("mark", DoubleType(), True),
])

output_schema = StructType([
    StructField("label", IntegerType(), True),
    StructField("start", DoubleType(), True),
    StructField("end", DoubleType(), True),
    StructField("id", StringType(), True),
])

kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka-1:9092,kafka-2:9092") \
    .option("spark.streaming.kafka.maxRatePerPartition", "1000") \
    .option("subscribe", "signal") \
    .option("startingOffsets", "earliest") \
    .load()

parsed_df = kafka_df.select(
    F.col('key'), 
    F.col('partition'),
    F.from_json(F.col("value").cast("string"), signal_schema).alias("data")
) \
.select(
    F.col('key'), 
    F.col('partition'), 
    F.col('data.*')
)

predictions_stream = parsed_df \
    .groupBy("device_id") \
    .applyInPandasWithState(
        func=aggregateWindow,
        outputStructType=output_schema,
        stateStructType=state_schema,
        outputMode="append",
        timeoutConf=GroupStateTimeout.NoTimeout
    )

query = predictions_stream \
    .writeStream \
    .foreachBatch(send_predictions) \
    .start()

query.awaitTermination()
