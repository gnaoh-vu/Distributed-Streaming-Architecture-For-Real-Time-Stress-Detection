import schedule
import logging 
import time
import subprocess

logging.basicConfig(
    filename='spark_job_scheduler.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_spark_job():
    logging.info("Starting Spark job submission...")

    cmd = [
        "spark-submit",
        "--master", "yarn",
        "--deploy-mode", "cluster",
        "--conf", "spark.pyspark.python=./environment/bin/python",
        "--archives", "hdfs:///shared/venv3.11.tar.gz#environment",
        "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
        "--num-executors", "2",
        "--executor-cores", "1",
        "--executor-memory", "1G",
        "/jobs/kafka_hdfs.py"
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logging.info("Spark job completed successfully.")
        logging.debug(f"Output: {result.stdout}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Spark job failed with return code {e.returncode}")
        logging.error(f"Error output: {e.stderr}")

schedule.every(15).minutes.do(run_spark_job)
logging.info("Python Spark Scheduler started.")

while True:
    schedule.run_pending()
    time.sleep(1)

