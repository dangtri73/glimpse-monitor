FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-ingest.txt ./
RUN python -m pip install --no-cache-dir -r requirements-ingest.txt

COPY app ./app
COPY scripts ./scripts

CMD ["python", "-m", "app.server"]
