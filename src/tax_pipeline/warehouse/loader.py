"""
loads validated batches into the warehouse using sql.
handles scd2 versioning, idempotent fact upserts, late-arriving facts
(as-of join), and correction auditing.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from tax_pipeline.quality.scorer import DQScore
from tax_pipeline.utils.logging import get_logger

logger = get_logger(__name__)

# descriptive attributes whose change creates a new scd2 version
_TRACKED = [
    "occupation",
    "postal_code",
    "housing_type",
    "residential_status",
    "filing_status",
    "number_of_dependents",
]
# sql predicate that is true when any tracked attribute differs
_CHANGED = " OR ".join(f"d.{c} IS DISTINCT FROM s.{c}" for c in _TRACKED)


class WarehouseLoader:
    """
    writes dimensions, fact, dq metrics, and corrections into duckdb.
    """

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.con = con

    def load_employers(self, employer_df: pd.DataFrame) -> None:
        """
        full-reload the employer dimension and add the default unknown row.
        """
        self.con.register("emp", employer_df)
        self.con.execute("DELETE FROM dim_employer")
        self.con.execute(
            """
            INSERT INTO dim_employer
            SELECT employer_id, company_name, uen, industry, address,
                   TRY_CAST(employee_count AS INTEGER)
            FROM emp
            """
        )
        self.con.execute(
            "INSERT INTO dim_employer VALUES "
            "('UNKNOWN', 'Unknown / Self-employed', NULL, NULL, NULL, NULL)"
        )
        self.con.unregister("emp")

    def load_batch(self, validated_df: pd.DataFrame, batch_date: str | None) -> None:
        """
        load one validated batch: scd2 dim_taxpayer, then fact (with audit).
        idempotent: re-running the same batch leaves the warehouse unchanged.
        """
        self.con.register("stg", validated_df)
        self._scd2_taxpayer(batch_date)
        self._audit_corrections(batch_date)
        self._upsert_fact(batch_date)
        self.con.unregister("stg")

    def _scd2_taxpayer(self, batch_date: str | None) -> None:
        # 1. brand-new taxpayers (first appearance): insert, valid_from = filing_date.
        #    covers new / late_arrival / any first-seen taxpayer regardless of record_type.
        self.con.execute(
            """
            INSERT INTO dim_taxpayer
            SELECT nextval('seq_taxpayer_sk'), s.taxpayer_id, s.nric, s.full_name, s.filing_status,
                   s.occupation, s.residential_status, s.postal_code, s.housing_type,
                   s.number_of_dependents,
                   TRY_CAST(s.filing_date AS DATE), DATE '9999-12-31', TRUE
            FROM stg s
            WHERE NOT EXISTS (SELECT 1 FROM dim_taxpayer d WHERE d.taxpayer_id = s.taxpayer_id)
            """
        )

        # 2. corrections fix the current version in place (the old value was wrong,
        #    not real history) - no new version is created.
        self.con.execute(
            """
            UPDATE dim_taxpayer SET
                nric = s.nric, full_name = s.full_name, filing_status = s.filing_status,
                occupation = s.occupation, residential_status = s.residential_status,
                postal_code = s.postal_code, housing_type = s.housing_type,
                number_of_dependents = s.number_of_dependents
            FROM stg s
            WHERE dim_taxpayer.taxpayer_id = s.taxpayer_id
              AND dim_taxpayer.is_current = TRUE
              AND s.record_type = 'correction'
            """
        )

        # 3. updates are real changes -> new scd2 version (only if a tracked attr changed).
        self.con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE chg AS
            SELECT s.* FROM stg s
            JOIN dim_taxpayer d ON d.taxpayer_id = s.taxpayer_id AND d.is_current = TRUE
            WHERE s.record_type = 'update' AND ({_CHANGED})
            """
        )
        self.con.execute(
            """
            UPDATE dim_taxpayer
            SET valid_to = TRY_CAST(? AS DATE), is_current = FALSE
            WHERE is_current = TRUE AND taxpayer_id IN (SELECT taxpayer_id FROM chg)
            """,
            [batch_date],
        )
        self.con.execute(
            """
            INSERT INTO dim_taxpayer
            SELECT nextval('seq_taxpayer_sk'), taxpayer_id, nric, full_name, filing_status,
                   occupation, residential_status, postal_code, housing_type, number_of_dependents,
                   TRY_CAST(? AS DATE), DATE '9999-12-31', TRUE
            FROM chg
            """,
            [batch_date],
        )

    def _audit_corrections(self, batch_date: str | None) -> None:
        # save old values before a correction overwrites them; only when values actually change
        self.con.execute(
            """
            INSERT INTO fact_corrections
            SELECT nextval('seq_correction_id'), f.taxpayer_id, f.assessment_year,
                   TRY_CAST(? AS DATE),
                   f.annual_income_sgd, f.chargeable_income_sgd, f.tax_payable_sgd,
                   f.tax_paid_sgd, f.total_reliefs_sgd
            FROM fact_tax_returns f
            JOIN stg s
              ON s.taxpayer_id = f.taxpayer_id
             AND TRY_CAST(s.assessment_year AS INTEGER) = f.assessment_year
            WHERE s.record_type = 'correction'
              AND (f.chargeable_income_sgd IS DISTINCT FROM TRY_CAST(s.chargeable_income_sgd AS DOUBLE)
                   OR f.tax_payable_sgd IS DISTINCT FROM TRY_CAST(s.tax_payable_sgd AS DOUBLE)
                   OR f.tax_paid_sgd IS DISTINCT FROM TRY_CAST(s.tax_paid_sgd AS DOUBLE)
                   OR f.total_reliefs_sgd IS DISTINCT FROM TRY_CAST(s.total_reliefs_sgd AS DOUBLE)
                   OR f.annual_income_sgd IS DISTINCT FROM TRY_CAST(s.annual_income_sgd AS DOUBLE))
              -- dedupe: don't log the same correction twice (idempotent on replay)
              AND NOT EXISTS (
                  SELECT 1 FROM fact_corrections fc
                  WHERE fc.taxpayer_id = f.taxpayer_id
                    AND fc.assessment_year = f.assessment_year
                    AND fc.old_annual_income_sgd     IS NOT DISTINCT FROM f.annual_income_sgd
                    AND fc.old_chargeable_income_sgd IS NOT DISTINCT FROM f.chargeable_income_sgd
                    AND fc.old_tax_payable_sgd        IS NOT DISTINCT FROM f.tax_payable_sgd
                    AND fc.old_tax_paid_sgd           IS NOT DISTINCT FROM f.tax_paid_sgd
                    AND fc.old_total_reliefs_sgd      IS NOT DISTINCT FROM f.total_reliefs_sgd)
            """,
            [batch_date],
        )

    def _upsert_fact(self, batch_date: str | None) -> None:
        # delete the keys in this batch, then re-insert: idempotent replace on (taxpayer, year)
        self.con.execute(
            """
            DELETE FROM fact_tax_returns
            WHERE (taxpayer_id, assessment_year) IN (
                SELECT taxpayer_id, TRY_CAST(assessment_year AS INTEGER) FROM stg)
            """
        )
        # taxpayer_sk uses the version valid as-of filing_date; falls back to current
        self.con.execute(
            """
            INSERT INTO fact_tax_returns
            SELECT s.taxpayer_id,
                   TRY_CAST(s.assessment_year AS INTEGER),
                   COALESCE(d_asof.taxpayer_sk, d_curr.taxpayer_sk),
                   COALESCE(e.employer_id, 'UNKNOWN'),
                   TRY_CAST(s.filing_date AS DATE),
                   TRY_CAST(? AS DATE),
                   s.record_type,
                   TRY_CAST(s.annual_income_sgd AS DOUBLE),
                   TRY_CAST(s.chargeable_income_sgd AS DOUBLE),
                   TRY_CAST(s.tax_payable_sgd AS DOUBLE),
                   TRY_CAST(s.tax_paid_sgd AS DOUBLE),
                   TRY_CAST(s.total_reliefs_sgd AS DOUBLE),
                   TRY_CAST(s.cpf_contributions_sgd AS DOUBLE),
                   TRY_CAST(s.foreign_income_sgd AS DOUBLE),
                   (s.record_type = 'correction')
            FROM stg s
            LEFT JOIN dim_taxpayer d_asof
              ON d_asof.taxpayer_id = s.taxpayer_id
             AND TRY_CAST(s.filing_date AS DATE) >= d_asof.valid_from
             AND TRY_CAST(s.filing_date AS DATE) <  d_asof.valid_to
            LEFT JOIN dim_taxpayer d_curr
              ON d_curr.taxpayer_id = s.taxpayer_id AND d_curr.is_current = TRUE
            LEFT JOIN dim_employer e ON e.employer_id = s.employer_id
            """,
            [batch_date],
        )

    def record_dq_metrics(self, batch: str, score: DQScore) -> None:
        """
        store this batch's per-domain dq scores (idempotent on re-run).
        """
        self.con.execute("DELETE FROM agg_data_quality_metrics WHERE batch = ?", [batch])
        for domain, value in score.scores.items():
            self.con.execute(
                "INSERT INTO agg_data_quality_metrics VALUES (?, ?, ?, ?, ?, now())",
                [batch, domain, value, score.passing_counts[domain], score.total_rows],
            )
