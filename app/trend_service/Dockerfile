FROM python:3.14

RUN apt update

RUN apt install -y openjdk-21-jdk

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

