"""
dev helper: print a quick overview of the duckdb warehouse.
run: python scripts/inspect_warehouse.py
"""

from __future__ import annotations

from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parents[1] / "warehouse" / "tax.duckdb"
TABLES = [
    "dim_taxpayer",
    "dim_employer",
    "fact_tax_returns",
    "agg_data_quality_metrics",
    "fact_corrections",
]


def main() -> None:
    if not DB.exists():
        print(f"no warehouse at {DB}\nbuild it first: python -m tax_pipeline.warehouse.build")
        return

    con = duckdb.connect(str(DB), read_only=True)
    print(f"warehouse: {DB}\n")
    for t in TABLES:
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t:26}: {n} rows")

    print("\n-- dim_taxpayer: SG001 history (scd2) --")
    print(con.execute(
        "SELECT taxpayer_sk, occupation, postal_code, valid_from, valid_to, is_current "
        "FROM dim_taxpayer WHERE taxpayer_id = 'SG001' ORDER BY valid_from"
    ).df().to_string(index=False))

    print("\n-- fact_tax_returns sample --")
    print(con.execute(
        "SELECT taxpayer_id, assessment_year, employer_id, tax_payable_sgd, is_corrected "
        "FROM fact_tax_returns ORDER BY taxpayer_id LIMIT 5"
    ).df().to_string(index=False))

    print("\n-- agg_data_quality_metrics --")
    print(con.execute(
        "SELECT batch, domain, score, passing_count, total_count "
        "FROM agg_data_quality_metrics ORDER BY batch, domain"
    ).df().to_string(index=False))

    print("\n-- fact_corrections (audit) --")
    print(con.execute(
        "SELECT taxpayer_id, assessment_year, old_tax_payable_sgd FROM fact_corrections"
    ).df().to_string(index=False))

    con.close()


if __name__ == "__main__":
    main()
