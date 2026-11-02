import pyspark
from pyspark.sql import *
from pyspark.sql.types import *
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = SparkSession.builder \
    .master("yarn") \
    .config('spark.ui.port', 4040) \
    .getOrCreate()

sc = spark.sparkContext
WINDOW_LENGTH_MIN = 5
OVERLAP_RATIO = 0.5
THRESHOLD=1.5

schema = StructType([
    StructField("patient_id", StringType(), True),
    StructField("eda", ArrayType(DoubleType()), True),
    StructField("ibi", ArrayType(DoubleType()), True),
    StructField("timestamp", TimestampType(), True),
])

df = spark.read \
    .schema(schema) \
    .parquet('/signals')

df.write \
.repartition(F.col('patient_id')) \
.mode("overwrite") \
.option('maxFileSize', "134217728") \
.partitionBy('patient_id') \
.parquet('/signals')
