"""
build the warehouse: process each batch in order (day1 -> day2 -> day3),
validating then loading into duckdb dimensions and fact.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from tax_pipeline.config import PROJECT_ROOT, Config
from tax_pipeline.ingestion import CsvBatchExtractor, JsonEmployerExtractor
from tax_pipeline.models import schema
from tax_pipeline.quality import DQScorer
from tax_pipeline.validation import Validator, build_rules
from tax_pipeline.warehouse.connection import get_connection, init_schema
from tax_pipeline.warehouse.loader import WarehouseLoader
from tax_pipeline.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = PROJECT_ROOT / "warehouse" / "tax.duckdb"


class WarehouseBuilder:
    """
    orchestrates extraction, validation, and warehouse loading per batch.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        self.validator = Validator(build_rules(self.config.validation))
        self.scorer = DQScorer()

    def build(self, con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
        """
        initialise schema, load employers once, then load each batch in order.
        """
        init_schema(con)
        loader = WarehouseLoader(con)

        employers = JsonEmployerExtractor(
            self.config.resolve(self.config.employer_json)
        ).extract()
        loader.load_employers(employers)

        for path in self.config.individual_files():
            self.load_batch_file(loader, path)
        return con

    def load_batch_file(self, loader: WarehouseLoader, path: Path) -> None:
        """
        validate and load a single batch file (re-usable for idempotency tests).
        """
        df = CsvBatchExtractor(path).extract()
        validated = self.validator.validate(df)
        score = self.scorer.score(validated)
        batch = path.stem.replace("individual_tax_returns_", "")
        loader.load_batch(validated, self._batch_date(validated))
        loader.record_dq_metrics(batch, score)
        logger.info("Loaded batch %s (%d rows)", batch, len(validated))

    @staticmethod
    def _batch_date(df: pd.DataFrame) -> str | None:
        # batch_date is uniform within a batch; day1 has none
        values = df[schema.BATCH_DATE].dropna()
        return str(values.iloc[0]) if len(values) else None


def main() -> None:
    DEFAULT_DB_PATH.parent.mkdir(exist_ok=True)
    if DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH.unlink()  # fresh build

    con = get_connection(DEFAULT_DB_PATH)
    WarehouseBuilder().build(con)

    print("\n=== Warehouse build complete ===")
    for table in ["dim_taxpayer", "dim_employer", "fact_tax_returns",
                  "agg_data_quality_metrics", "fact_corrections"]:
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:26}: {n} rows")

    print("\nSCD2 example - SG001 versions:")
    rows = con.execute(
        """
        SELECT taxpayer_sk, occupation, postal_code, valid_from, valid_to, is_current
        FROM dim_taxpayer WHERE taxpayer_id = 'SG001' ORDER BY valid_from
        """
    ).fetchall()
    for r in rows:
        print(f"  sk={r[0]} {r[1]:<26} {r[2]:<8} {r[3]} -> {r[4]}  current={r[5]}")

    con.close()


if __name__ == "__main__":
    main()
