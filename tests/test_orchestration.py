"""
tests for the prefect orchestration flow: batch resolution, the failure alert,
and an end-to-end run that loads the warehouse.
"""

from __future__ import annotations

import types

import pytest

import tax_pipeline.orchestration.flow as flow_mod
from tax_pipeline.orchestration.flow import _resolve_batches, alert_on_failure, run_pipeline
from tax_pipeline.warehouse.connection import get_connection


def test_resolve_batches_all_returns_every_file():
    assert len(_resolve_batches("all")) == 3


def test_resolve_batches_single_day():
    matches = _resolve_batches("day2")
    assert len(matches) == 1 and "day2" in matches[0].stem


def test_resolve_batches_unknown_raises():
    with pytest.raises(ValueError):
        _resolve_batches("day99")


def test_alert_hook_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(flow_mod, "ALERT_DIR", tmp_path / "alerts")
    flow_run = types.SimpleNamespace(name="test-run")
    state = types.SimpleNamespace(type="FAILED")
    alert_on_failure(None, flow_run, state)

    files = list((tmp_path / "alerts").glob("*.txt"))
    assert len(files) == 1
    assert "PIPELINE FAILURE" in files[0].read_text(encoding="utf-8")


def test_flow_end_to_end_loads_warehouse(tmp_path):
    db = str(tmp_path / "t.duckdb")
    run_pipeline("all", db)

    con = get_connection(db)
    fact = con.execute("SELECT count(*) FROM fact_tax_returns").fetchone()[0]
    metrics = con.execute("SELECT count(*) FROM agg_data_quality_metrics").fetchone()[0]
    con.close()

    assert fact == 161           # one row per taxpayer x year
    assert metrics == 9          # 3 batches x 3 domains
