FROM python:3.11-slim

RUN useradd -m -u 1000 user
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 libstdc++6 libatomic1 && rm -rf /var/lib/apt/lists/*

COPY --chown=user backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user backend/app ./app

USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
