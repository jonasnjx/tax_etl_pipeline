# container image for the tax pipeline.
# python 3.12-slim: broad wheel support for pandas/duckdb/prefect; code targets 3.11+.
FROM python:3.12-slim

WORKDIR /app

# install deps first so the layer caches when only source changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# application code and config (data/ and warehouse/ come in as mounted volumes)
COPY src/ ./src/
COPY config/ ./config/

ENV PYTHONPATH=/app/src

# default: run the full backfill through the prefect flow
CMD ["python", "-m", "tax_pipeline.orchestration.flow", "all"]
