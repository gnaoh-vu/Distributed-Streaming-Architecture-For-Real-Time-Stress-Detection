FROM python:3.14

RUN apt update

RUN apt install -y openjdk-21-jdk

RUN wget -O /spark.tgz https://dlcdn.apache.org/spark/spark-4.3.0/spark-4.3.0-bin-hadoop3.tgz

RUN tar -xzf /spark.tgz -C /opt

RUN mv /opt/spark-4.3.0-bin-hadoop3 /opt/spark

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

