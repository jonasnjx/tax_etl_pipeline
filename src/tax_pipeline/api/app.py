"""
fastapi service exposing the warehouse data.
endpoints: tax summary by demographic, current dq metrics, taxpayer lookup.
reads the duckdb warehouse read-only. api-key auth via the X-API-Key header.
openapi docs are served automatically at /docs.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

from tax_pipeline.config import PROJECT_ROOT, Config

_cfg = Config.load()
API_KEY = _cfg.api.get("api_key", "for-demo-purpose-only")
DEFAULT_DB_PATH = PROJECT_ROOT / "warehouse" / "tax.duckdb"

app = FastAPI(
    title="Tax Data API",
    description="Read-only access to the tax warehouse: demographics, data quality, taxpayers.",
    version="1.0.0",
)


def _db_path() -> str:
    # env override lets tests point at a temporary warehouse
    return os.environ.get("TAX_DB_PATH", str(DEFAULT_DB_PATH))


def get_con():
    """
    yield a read-only duckdb connection for one request; 503 if not built yet.
    """
    path = _db_path()
    if not Path(path).exists():
        raise HTTPException(status_code=503, detail="warehouse not built yet")
    con = duckdb.connect(path, read_only=True)
    try:
        yield con
    finally:
        con.close()


# registering the scheme this way adds an "Authorize" button to the /docs page
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    """
    reject requests without the correct X-API-Key header.
    """
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def _rows(con, sql: str, params: list | None = None) -> list[dict]:
    # duckdb returns native python types (date/int/float/str) -> json-friendly
    cur = con.execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


class GroupBy(str, Enum):
    occupation = "occupation"
    residential_status = "residential_status"
    housing_type = "housing_type"


@app.get("/health")
def health() -> dict:
    """
    liveness check (no auth).
    """
    return {"status": "ok"}


@app.get("/tax-summary", dependencies=[Depends(require_api_key)])
def tax_summary(
    group_by: GroupBy,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    con=Depends(get_con),
) -> dict:
    """
    aggregated tax figures grouped by a demographic dimension, paginated.
    """
    col = group_by.value  # safe: constrained to the enum, not free text
    results = _rows(
        con,
        f"""
        SELECT d.{col} AS group_value,
               count(*) AS num_returns,
               round(sum(f.tax_payable_sgd), 2) AS total_tax_payable,
               round(avg(f.annual_income_sgd), 2) AS avg_annual_income
        FROM fact_tax_returns f
        JOIN dim_taxpayer d ON f.taxpayer_sk = d.taxpayer_sk
        GROUP BY d.{col}
        ORDER BY total_tax_payable DESC NULLS LAST
        LIMIT ? OFFSET ?
        """,
        [limit, offset],
    )
    return {"group_by": col, "limit": limit, "offset": offset, "results": results}


@app.get("/data-quality", dependencies=[Depends(require_api_key)])
def data_quality(con=Depends(get_con)) -> dict:
    """
    current dq score per domain (the most recently loaded batch's score).
    """
    results = _rows(
        con,
        """
        SELECT domain, score, passing_count, total_count, batch, computed_at
        FROM agg_data_quality_metrics
        QUALIFY row_number() OVER (PARTITION BY domain ORDER BY computed_at DESC) = 1
        ORDER BY domain
        """,
    )
    return {"results": results}


@app.get("/taxpayers/{taxpayer_id}", dependencies=[Depends(require_api_key)])
def taxpayer_detail(taxpayer_id: str, con=Depends(get_con)) -> dict:
    """
    one taxpayer's current profile plus their tax return(s). 404 if unknown.
    """
    profile = _rows(
        con,
        """
        SELECT taxpayer_id, nric, full_name, occupation, residential_status,
               postal_code, housing_type
        FROM dim_taxpayer WHERE taxpayer_id = ? AND is_current = TRUE
        """,
        [taxpayer_id],
    )
    if not profile:
        raise HTTPException(status_code=404, detail=f"taxpayer {taxpayer_id} not found")

    returns = _rows(
        con,
        """
        SELECT assessment_year, filing_date, annual_income_sgd, chargeable_income_sgd,
               tax_payable_sgd, tax_paid_sgd, employer_id, is_corrected
        FROM fact_tax_returns WHERE taxpayer_id = ?
        ORDER BY assessment_year
        """,
        [taxpayer_id],
    )
    return {"profile": profile[0], "returns": returns}
