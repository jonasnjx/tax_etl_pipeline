"""
prefect orchestration flow.
stages: ingest -> validate + score -> load -> dq report.
runs one batch (batch_date='day1'/'day2'/'day3') or backfills all in order
('all'). tasks retry with backoff; a final failure writes an alert file.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from prefect import flow, task
from prefect.logging import get_run_logger

from tax_pipeline.config import PROJECT_ROOT, Config
from tax_pipeline.ingestion import CsvBatchExtractor, JsonEmployerExtractor
from tax_pipeline.models import schema
from tax_pipeline.quality import DQScore, DQScorer
from tax_pipeline.validation import Validator, build_rules
from tax_pipeline.warehouse.connection import get_connection, init_schema
from tax_pipeline.warehouse.loader import WarehouseLoader

_cfg = Config.load()
_RETRIES = _cfg.orchestration.get("retries", 3)
_RETRY_DELAYS = _cfg.orchestration.get("retry_delay_seconds", [10, 30, 60])

DEFAULT_DB_PATH = PROJECT_ROOT / "warehouse" / "tax.duckdb"
ALERT_DIR = PROJECT_ROOT / "logs" / "alerts"


def _resolve_batches(batch_date: str) -> list[Path]:
    """
    map the batch_date parameter to the file(s) to process, in order.
    'all' = backfill every batch; otherwise the single matching day.
    """
    files = _cfg.individual_files()
    if batch_date == "all":
        return files
    matches = [p for p in files if batch_date in p.stem]
    if not matches:
        raise ValueError(f"no batch file found for batch_date={batch_date!r}")
    return matches


def _batch_date_value(df: pd.DataFrame) -> str | None:
    values = df[schema.BATCH_DATE].dropna()
    return str(values.iloc[0]) if len(values) else None


def alert_on_failure(flow, flow_run, state) -> None:
    """
    mock notification: on final flow failure, write an alert file and log it.
    """
    ALERT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ALERT_DIR / f"alert_{stamp}.txt"
    path.write_text(
        f"PIPELINE FAILURE\nflow_run: {getattr(flow_run, 'name', '?')}\n"
        f"state: {getattr(state, 'type', '?')}\ntime: {stamp}\n",
        encoding="utf-8",
    )


@task(retries=_RETRIES, retry_delay_seconds=_RETRY_DELAYS)
def setup_warehouse(db_path: str) -> None:
    """
    ensure the schema exists and (re)load the employer dimension.
    """
    con = get_connection(db_path)
    init_schema(con)
    employers = JsonEmployerExtractor(_cfg.resolve(_cfg.employer_json)).extract()
    WarehouseLoader(con).load_employers(employers)
    con.close()


@task(retries=_RETRIES, retry_delay_seconds=_RETRY_DELAYS)
def ingest(path: Path) -> pd.DataFrame:
    """
    stage 1: extract one batch file into the canonical schema.
    """
    return CsvBatchExtractor(path).extract()


@task(retries=_RETRIES, retry_delay_seconds=_RETRY_DELAYS)
def validate_and_score(df: pd.DataFrame) -> tuple[pd.DataFrame, DQScore]:
    """
    stage 2: run the validation rules and compute dq scores.
    """
    validated = Validator(build_rules(_cfg.validation)).validate(df)
    return validated, DQScorer().score(validated)


@task(retries=_RETRIES, retry_delay_seconds=_RETRY_DELAYS)
def load(db_path: str, validated: pd.DataFrame, batch_date: str | None) -> None:
    """
    stage 3: load the batch into the warehouse (scd2 dims + fact).
    """
    con = get_connection(db_path)
    WarehouseLoader(con).load_batch(validated, batch_date)
    con.close()


@task(retries=_RETRIES, retry_delay_seconds=_RETRY_DELAYS)
def dq_report(db_path: str, batch: str, score: DQScore) -> dict:
    """
    stage 4: persist this batch's dq scores and log them.
    """
    con = get_connection(db_path)
    WarehouseLoader(con).record_dq_metrics(batch, score)
    con.close()
    get_run_logger().info("DQ scores for %s: %s", batch, score.scores)
    return score.scores


@flow(name="tax-pipeline", on_failure=[alert_on_failure])
def run_pipeline(batch_date: str = "all", db_path: str = str(DEFAULT_DB_PATH)) -> None:
    """
    orchestrate the four stages for the requested batch(es).
    tasks are called in order, so each runs only after the previous succeeds.
    """
    setup_warehouse(db_path)
    for path in _resolve_batches(batch_date):
        batch = path.stem.replace("individual_tax_returns_", "")
        df = ingest(path)
        validated, score = validate_and_score(df)
        load(db_path, validated, _batch_date_value(validated))
        dq_report(db_path, batch, score)


def main() -> None:
    import sys

    batch_date = sys.argv[1] if len(sys.argv) > 1 else "all"
    DEFAULT_DB_PATH.parent.mkdir(exist_ok=True)
    run_pipeline(batch_date)


if __name__ == "__main__":
    main()
