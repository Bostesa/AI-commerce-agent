# Backend Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Warm up sentence transformers model cache at build time to avoid cold start downloads
RUN python - <<'PY'
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer('clip-ViT-B-32')
except Exception as e:
    print('Model prefetch skipped:', e)
PY

COPY . .

# Create evaluation results directory with proper permissions
RUN mkdir -p /app/evaluation/results && \
    chmod -R 755 /app/evaluation

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python","-c","import urllib.request,sys;sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health',timeout=3).getcode()==200 else sys.exit(1)"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
