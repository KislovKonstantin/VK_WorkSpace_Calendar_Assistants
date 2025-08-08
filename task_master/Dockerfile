FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY task_master.py .

RUN mkdir /data

ENTRYPOINT ["python", "task_master.py"]