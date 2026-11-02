import pyspark
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import *
from pyspark.sql.window import Window

spark = (
    SparkSession.builder.master("yarn")
    .config("spark.ui.port", 4040)
    .getOrCreate()
)

WINDOW_LENGTH_MIN = 5
OVERLAP_RATIO = 0.5
THRESHOLD = 1.0

schema = StructType(
    [
        StructField("patient_id", StringType(), True),
        StructField("eda", ArrayType(DoubleType()), True),
        StructField("ibi", ArrayType(DoubleType()), True),
        StructField("timestamp", TimestampType(), True),
    ]
)

df = spark.read.schema(schema).parquet("/signals")

window_df = (
    df.groupBy(
        F.col("patient_id"),
        F.window(
            timeColumn="timestamp",
            windowDuration=f"{WINDOW_LENGTH_MIN} minutes",
            slideDuration=f"{int((1-OVERLAP_RATIO)*WINDOW_LENGTH_MIN)} minutes",
        ),
    )
    .agg(
        F.array_mean(F.flatten(F.collect_list("eda"))).alias("w_mean_eda"),
        F.array_sort(F.flatten(F.collect_list("ibi"))).alias(
            "w_ibi_timestamps"
        ),
    )
    .filter(F.size("w_ibi_timestamps") > 2)
    .withColumn(
        "w_ibi",
        F.zip_with(
            F.slice(
                F.col("w_ibi_timestamps"), 2, F.size(F.col("w_ibi_timestamps"))
            ),
            F.slice(
                F.col("w_ibi_timestamps"),
                1,
                F.size(F.col("w_ibi_timestamps")) - 1,
            ),
            lambda x, y: x - y,
        ),
    )
    .withColumn(
        "w_ibi_diffs",
        F.zip_with(
            F.slice(F.col("w_ibi"), 2, F.size(F.col("w_ibi"))),
            F.slice(F.col("w_ibi"), 1, F.size(F.col("w_ibi")) - 1),
            lambda next_i, prev_i: next_i - prev_i,
        ),
    )
    .select(
        F.col("patient_id"),
        F.col("window.start").alias("window_start"),
        F.col("w_mean_eda"),
        F.sqrt(
            F.aggregate(
                F.transform(
                    F.col("w_ibi_diffs"), lambda diff: diff * diff
                ),
                F.lit(0.0),
                lambda acc, sqd: acc + sqd,
            )
            / F.size(F.col("w_ibi_diffs"))
        ).alias("w_hrv_rmssd"),
    )
)

patient_window = Window.partitionBy("patient_id")

window_stats = window_df.select(
    F.col("patient_id"),
    F.col("window_start"),
    F.col("w_mean_eda"),
    F.col("w_hrv_rmssd"),
    # Z-score normalization components
    (
        (F.col("w_mean_eda") - F.avg("w_mean_eda").over(patient_window))
        / (F.stddev_samp("w_mean_eda").over(patient_window) + 1e-5)
    ).alias("z_eda"),
    (
        (F.col("w_hrv_rmssd") - F.avg("w_hrv_rmssd").over(patient_window))
        / (F.stddev_samp("w_hrv_rmssd").over(patient_window) + 1e-5)
    ).alias("z_hrv"),
)

dysregulated_df = window_stats.withColumn(
    "is_dysregulated",
    (F.col("z_eda") > THRESHOLD) & (F.col("z_hrv") < -THRESHOLD),
).withColumn(
    # Severity score: product of sympathetic elevation and parasympathetic suppression
    "severity_score",
    F.when(
        F.col("is_dysregulated"),
        F.abs(F.col("z_eda")) * F.abs(F.col("z_hrv")),
    ).otherwise(0.0),
)

ans_weekly_df = (
    dysregulated_df.groupBy(
        F.col("patient_id"),
        F.window(
            timeColumn="window_start",
            windowDuration="7 days",
            slideDuration="7 days",
        ),
    )
    .agg(
        F.count("*").alias("total_windows"),
        F.sum(
            F.when(F.col("is_dysregulated"), 1).otherwise(0)
        ).alias("dysregulated_windows"),
        F.sum("severity_score").alias("weekly_dysregulation_severity"),
    )
    .select(
        F.col("patient_id"),
        F.col("window.start").alias("week_start"),
        F.col("dysregulated_windows"),
        (
            F.col("dysregulated_windows") / F.col("total_windows")
        ).alias("dysregulation_ratio"),
        F.col("weekly_dysregulation_severity"),
    )
)

ans_weekly_df.show()
