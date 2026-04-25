FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=180

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    sox \
    libsox-dev \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN bash -lc 'set -e; \
    for i in 1 2 3 4 5; do \
        echo "pip install attempt $i/5"; \
        pip install --no-cache-dir --retries 25 --timeout 240 --prefer-binary -r /app/requirements.txt && exit 0; \
        echo "pip install failed, retrying in 15s..."; \
        sleep 15; \
    done; \
    echo "pip install failed after 5 attempts"; \
    exit 1'

COPY app /app/app
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
