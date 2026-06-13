"""
tests for the warehouse loader: scd2, idempotency, corrections, late arrivals,
and the unknown-employer fallback. these run against the real data via duckdb.
"""

from __future__ import annotations

import pytest

from tax_pipeline.warehouse.build import WarehouseBuilder
from tax_pipeline.warehouse.connection import get_connection

TABLES = [
    "dim_taxpayer",
    "dim_employer",
    "fact_tax_returns",
    "agg_data_quality_metrics",
    "fact_corrections",
]


def _counts(con) -> dict[str, int]:
    return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}


@pytest.fixture(scope="module")
def con():
    c = get_connection(":memory:")
    WarehouseBuilder().build(c)
    yield c
    c.close()


def test_scd2_creates_new_version_on_update(con):
    # SG001 changed job + address in day2 -> two versions, one current
    rows = con.execute(
        """
        SELECT occupation, valid_from, valid_to, is_current
        FROM dim_taxpayer WHERE taxpayer_id = 'SG001' ORDER BY valid_from
        """
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][3] is False and rows[1][3] is True       # old closed, new current
    assert rows[0][2] == rows[1][1]                          # valid_to of v1 == valid_from of v2


def test_only_one_current_version_per_taxpayer(con):
    dupes = con.execute(
        """
        SELECT taxpayer_id, count(*) FROM dim_taxpayer
        WHERE is_current = TRUE GROUP BY taxpayer_id HAVING count(*) > 1
        """
    ).fetchall()
    assert dupes == []


def test_correction_fixes_dimension_in_place(con):
    # SG155's correction fixed a bad postal code; should be ONE version, value fixed
    rows = con.execute(
        "SELECT postal_code, is_current FROM dim_taxpayer WHERE taxpayer_id = 'SG155'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "249567"          # corrected in place, not 'BADPOST'


def test_correction_updates_fact_and_writes_audit(con):
    # SG003's correction changed money values -> fact flagged + old value audited
    is_corrected = con.execute(
        "SELECT is_corrected FROM fact_tax_returns WHERE taxpayer_id = 'SG003'"
    ).fetchone()[0]
    assert is_corrected is True
    audit = con.execute(
        "SELECT count(*) FROM fact_corrections WHERE taxpayer_id = 'SG003'"
    ).fetchone()[0]
    assert audit == 1


def test_late_arrival_linked_to_a_taxpayer_version(con):
    # SG044 arrived late in day3; must be in the fact with a resolved taxpayer_sk
    row = con.execute(
        "SELECT taxpayer_sk, record_type FROM fact_tax_returns WHERE taxpayer_id = 'SG044'"
    ).fetchone()
    assert row is not None
    assert row[0] is not None
    assert row[1] == "late_arrival"


def test_unmatched_employer_defaults_to_unknown(con):
    # the unknown row exists and some returns point at it
    has_unknown = con.execute(
        "SELECT count(*) FROM dim_employer WHERE employer_id = 'UNKNOWN'"
    ).fetchone()[0]
    assert has_unknown == 1
    unmatched = con.execute(
        "SELECT count(*) FROM fact_tax_returns WHERE employer_id = 'UNKNOWN'"
    ).fetchone()[0]
    assert unmatched > 0


def test_fact_grain_one_row_per_taxpayer_year(con):
    dupes = con.execute(
        """
        SELECT taxpayer_id, assessment_year, count(*) FROM fact_tax_returns
        GROUP BY taxpayer_id, assessment_year HAVING count(*) > 1
        """
    ).fetchall()
    assert dupes == []


def test_idempotent_full_rebuild():
    # running every batch again on the same warehouse must not change anything
    c = get_connection(":memory:")
    builder = WarehouseBuilder()
    builder.build(c)
    before = _counts(c)
    builder.build(c)            # full replay
    after = _counts(c)
    assert before == after
    c.close()


def test_idempotent_single_batch_rerun():
    # re-running just the last batch must not change row counts
    c = get_connection(":memory:")
    builder = WarehouseBuilder()
    builder.build(c)
    before = _counts(c)
    from tax_pipeline.warehouse.loader import WarehouseLoader
    day3 = [p for p in builder.config.individual_files() if "day3" in p.name][0]
    builder.load_batch_file(WarehouseLoader(c), day3)
    after = _counts(c)
    assert before == after
    c.close()
