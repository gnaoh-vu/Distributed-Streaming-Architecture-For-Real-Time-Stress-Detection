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
    .parquet('/data/signals')

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

window_stat_df = window_df \
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
)

week_df = window_stat_df.groupBy(
    F.col('patient_id'),
    F.col('mean_eda'),
    F.col('std_eda'),
    F.col('median_ibi'),
    F.col('std_ibi'),
    F.col('mean_hrv'),
    F.col('std_hrv'),
    F.window(
        timeColumn="window_start", 
        windowDuration=f"7 days", 
        slideDuration=f"7 days"
    )
) \
.agg(
    F.sum(
        F.when(F.col('w_mean_eda') > 2*F.col('std_eda'), F.col('w_mean_eda'))
    ).alias('auc_eda'),

    F.sum(
        F.when(F.col('w_median_ibi') > 2*F.col('std_ibi'), F.col('w_median_ibi'))
    ).alias('auc_ibi'),

    F.sum(
        F.when(F.col('w_hrv_rmssd') > 2*F.col('std_hrv'), F.col('w_hrv_rmssd'))
    ).alias('auc_hrv'),
) \
.withColumn('window_start', F.col('window.start'))

window_spec = Window.partitionBy('patient_id').orderBy('window_start')
result_df = week_df \
.select(
    F.col('*'),
    F.lag('auc_eda', 1).over(window_spec).alias('prev_auc_eda'),
    F.lag('auc_ibi', 1).over(window_spec).alias('prev_auc_ibi'),
    F.lag('auc_hrv', 1).over(window_spec).alias('prev_auc_hrv'),
) \
.select(
    F.col('patient_id'),
    F.col('window_start'),

    (F.when(F.col('prev_auc_eda').isNull(), 0)
      .otherwise((F.col('auc_eda') - F.col('prev_auc_eda')) / (F.col('prev_auc_eda') + 1e-5))
    ).alias('eda_improv'),

    (F.when(F.col('prev_auc_ibi').isNull(), 0)
      .otherwise((F.col('auc_ibi') - F.col('prev_auc_ibi')) / (F.col('prev_auc_ibi') + 1e-5))
    ).alias('ibi_improv'),

    (F.when(F.col('prev_auc_hrv').isNull(), 0)
      .otherwise((F.col('auc_hrv') - F.col('prev_auc_hrv')) / (F.col('prev_auc_hrv') + 1e-5))
    ).alias('hrv_improv'),
)

result_df.show()

result_df.write \
    .mode('overwrite') \
    .csv('/analyses/stress_load.csv')
