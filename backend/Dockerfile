FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole project (backend + ml_pipeline both needed)
COPY backend/ /app/backend/
COPY ml_pipeline/ /app/ml_pipeline/

# Run ML pipeline setup on build (trains models from real data)
# The CSV must be present at ml_pipeline/data/raw/astram_event_data.csv
RUN cd /app && python -m ml_pipeline.data_loader && \
    python -m ml_pipeline.feature_engineer && \
    python -m ml_pipeline.train && \
    python -m ml_pipeline.event_data_loader && \
    python -m ml_pipeline.train_event_model

WORKDIR /app/backend
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
