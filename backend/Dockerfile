FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s \
  CMD python -c "import urllib.request; exit(0 if urllib.request.urlopen('http://localhost:${PORT:-8000}/api/v1/health').status == 200 else 1)"
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
