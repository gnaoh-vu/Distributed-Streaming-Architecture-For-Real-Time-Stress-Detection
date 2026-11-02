import pyspark
from pyspark.sql import *
from pyspark.sql.types import *
from pyspark.sql import functions as F
from pyspark.sql.streaming.state import GroupStateTimeout

spark = SparkSession.builder \
    .master("yarn") \
    .config('spark.ui.port', 4040) \
    .getOrCreate()


signal_schema = StructType([
    StructField("patient_id", StringType(), True),
    StructField("eda", ArrayType(DoubleType()), True),
    StructField("ibi", ArrayType(DoubleType()), True),
    StructField("timestamp", DoubleType(), True),
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
) \
.withColumn("timestamp", F.from_unixtime(F.col("timestamp")).cast("timestamp")) \
.withColumn("year", F.year("timestamp")) \
.withColumn("month", F.month("timestamp")) \
.withColumn("day", F.dayofmonth("timestamp"))

query = parsed_df.writeStream \
    .format("parquet") \
    .option("path", "/signals") \
    .option("checkpointLocation", "/tmp/checkpoint-kafka2hdfs") \
    .partitionBy('patient_id') \
    .trigger(availableNow=True) \
    .start()

query.awaitTermination()
