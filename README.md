# ETL Pipeline Design (Sample Tax Data)

![CI](https://github.com/jonasnjx/tax_etl_pipeline/actions/workflows/ci.yml/badge.svg)

Ingests individual tax-return data, enforces data quality, and loads
a dimensional warehouse for analytics. Comes with orchestration, REST API, and documentation on cloud architecture design for scaling.

Built in Python with DuckDB, Prefect, and FastAPI

## Features
- **Ingests** daily individual CSV batches + an employer JSON, handles schema evolution and uncleaned data
- **Validates** against 6 data quality rules and gives overall quality scores across 3 domains (completeness, validity, accuracy)
- **Loads** a DuckDB warehouse with SCD2 history, idempotent incremental loading, late-arrival handling, and correction auditing
- **Orchestrates** with Prefect (retries, alerts)
- **Exposes** the data through FastAPI

## Quickstart
```bash
python -m pip install -r requirements.txt
export PYTHONPATH=src                 # windows powershell: $env:PYTHONPATH = "src"

# build the warehouse (validate + load all batches)
python -m tax_pipeline.warehouse.build

# or run it through the orchestrator: all batches, or a single day
python -m tax_pipeline.orchestration.flow all

# run the tests (63: the 6 rules, dq scoring, scd2, idempotency, corrections, late arrivals, api)
python -m pytest
```

Run the whole pipeline in a container instead:
```bash
docker compose up --build
```

The test suite also runs automatically on every push via GitHub Actions (`.github/workflows/ci.yml`).

## Access the data
**REST API** - start it, open docs at `http://localhost:8000/docs`:
```bash
python -m uvicorn tax_pipeline.api.app:app --port 8000
```
The three data endpoints below need the header `X-API-Key: for-demo-purpose-only` (`/health` is open):
- `GET /tax-summary?group_by=occupation|residential_status|housing_type` - tax aggregated by demographic
- `GET /data-quality` - current DQ score per domain
- `GET /taxpayers/{taxpayer_id}` - a taxpayer's profile and return(s)

**Directly** - the warehouse is a DuckDB file at `warehouse/tax.duckdb`:
```bash
python scripts/inspect_warehouse.py            # prints a quick overview
```

## Project structure
```
src/tax_pipeline/
  models/         canonical schema + dq domains
  ingestion/      csv + json extractors
  validation/     the 6 rules + validator
  quality/        dq scoring
  warehouse/      duckdb schema, loader (scd2/upsert), build
  orchestration/  prefect flow
  api/            fastapi service
config/           pipeline settings (paths, rules, retries, api key)
data/             raw source (read-only)
docs/             technical documentation
tests/            63 tests
```

## Documentation
[`docs/technical-design.md`](docs/technical-design.md) covers:
- Architecture, components, data model, and technology rationale
- Scalability analysis and cloud architecture
- Assumptions and design decisions
