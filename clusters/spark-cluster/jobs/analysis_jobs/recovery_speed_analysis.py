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

window_df = df.groupBy(
    F.col('patient_id'),
    F.window(
        timeColumn="timestamp", 
        windowDuration=f"{WINDOW_LENGTH_MIN} minutes", 
        slideDuration=f"{int((1-OVERLAP_RATIO)*WINDOW_LENGTH_MIN)} minutes"
    )
) \
.agg(
    F.flatten(F.collect_list('eda')).alias('w_eda'),
    F.array_sort(F.flatten(F.collect_list('ibi'))).alias('w_ibi')
) \
.filter(F.size('w_ibi') > 2) \
.withColumn(
    'w_ibi',
    F.zip_with(
        F.slice(F.col('w_ibi'), 2, F.size(F.col('w_ibi')) - 1),
        F.slice(F.col('w_ibi'), 1, F.size(F.col('w_ibi')) - 1),
        lambda x, y: x - y
    )
) \
.withColumn(
    "w_ibi_diffs",
    F.zip_with(
        F.slice(F.col("w_ibi"), 2, F.size(F.col("w_ibi")) - 1),
        F.slice(F.col("w_ibi"), 1, F.size(F.col("w_ibi")) - 1),
        lambda next_ibi, prev_ibi: next_ibi - prev_ibi,
    ),
) \
.select(
    F.col('patient_id'),
    F.col('window.start').alias('window_start'),
    F.col('window.end').alias('window_end'),
    F.col('w_eda'),
    F.col('w_ibi'),

    (F.aggregate(
        F.col('w_eda'),
        F.lit(0.0),
        lambda acc, e: acc + (e / F.size('w_eda'))
    )).alias('w_mean_eda'),

    F.element_at(
        F.array_sort(F.col('w_ibi')),
        (F.size(F.col("w_ibi")) / 2).cast("int") + 1
    ).alias('w_median_ibi'),

    F.sqrt(
        F.aggregate(
            F.transform(
                F.col("w_ibi_diffs"), lambda diff: diff * diff
            ),
            F.lit(0.0),
            lambda acc, sq_diff: acc + sq_diff,
        ) / F.size(F.col("w_ibi_diffs"))
    ).alias("w_hrv_rmssd"),
)

patient_window = Window.partitionBy('patient_id')

joined = window_df \
.select(
    F.col('patient_id'),
    F.col('window_start'),
    F.col("w_mean_eda"),
    F.col("w_median_ibi"),
    F.col("w_hrv_rmssd"),

    F.avg("w_mean_eda").over(patient_window).alias("mean_eda"),
    F.stddev_samp("w_mean_eda").over(patient_window).alias("std_eda"),

    F.percentile_approx("w_median_ibi", 0.5).over(patient_window).alias( "median_ibi"),
    F.stddev_samp("w_median_ibi").over(patient_window).alias("std_ibi"),

    F.avg("w_hrv_rmssd").over(patient_window).alias("mean_hrv"),
    F.stddev_samp("w_hrv_rmssd").over(patient_window).alias("std_hrv"),
) \
.withColumn(
    'is_exceeding',
    ((F.abs(F.col('w_mean_eda') - F.col('std_eda')) / (F.col('std_eda') + 1e-5)) > THRESHOLD) &
    ((F.abs(F.col('w_median_ibi') - F.col('std_ibi')) / (F.col('std_ibi') + 1e-5)) > THRESHOLD) &
    ((F.abs(F.col('w_hrv_rmssd') - F.col('std_hrv')) / (F.col('std_hrv') + 1e-5)) > THRESHOLD)
)

window_spec = Window.partitionBy('patient_id').orderBy('window_start')
cumulative_window = Window.partitionBy('patient_id').orderBy('window_start').rowsBetween(Window.unboundedPreceding, Window.currentRow)

STEP = int(WINDOW_LENGTH_MIN * (1 - OVERLAP_RATIO))
LIMIT = int(WINDOW_LENGTH_MIN / STEP) * STEP

joined = joined \
.filter(F.col('is_exceeding') == True) \
.withColumn('prev_window_start', F.lag('window_start', 1).over(window_spec)) \
.withColumn(
    'is_new_region', 
    F.when(F.col('prev_window_start').isNull(), 1)
     .when(
        (F.col('window_start').cast('long') - F.col('prev_window_start').cast('long')) > LIMIT * 60,
        1
      )
     .otherwise(0)
) \
.withColumn('region_id', F.sum(F.col('is_new_region')).over(cumulative_window))

result_df = joined \
    .groupBy(
        F.col('patient_id'),
        F.col('region_id')
    ) \
    .agg(
        F.min(F.col('window_start')).alias('region_start'),
        F.count('region_id').alias('number_consecutive_abnormal_windows')
    )
    # .where(F.col('number_consecutive_abnormal_windows') >= 6)

result_df.show()
