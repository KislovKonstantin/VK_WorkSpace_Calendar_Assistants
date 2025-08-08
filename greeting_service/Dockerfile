FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY greeting_service.py .

RUN mkdir /data

ENTRYPOINT ["python", "greeting_service.py"]