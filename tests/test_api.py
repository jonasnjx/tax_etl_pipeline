"""
tests for the rest api: auth, the three endpoints, pagination/validation, errors.
builds a temporary warehouse and points the api at it via TAX_DB_PATH.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from tax_pipeline.warehouse.build import WarehouseBuilder
from tax_pipeline.warehouse.connection import get_connection

HEADERS = {"X-API-Key": "for-demo-purpose-only"}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("wh") / "t.duckdb"
    con = get_connection(str(db))
    WarehouseBuilder().build(con)
    con.close()
    os.environ["TAX_DB_PATH"] = str(db)

    from tax_pipeline.api.app import app

    return TestClient(app)


def test_health_needs_no_auth(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_endpoint_requires_api_key(client):
    assert client.get("/data-quality").status_code == 401


def test_data_quality_returns_three_domains(client):
    r = client.get("/data-quality", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()["results"]) == 3


def test_tax_summary_by_occupation(client):
    r = client.get("/tax-summary?group_by=occupation", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["group_by"] == "occupation"
    assert len(body["results"]) > 0
    assert "total_tax_payable" in body["results"][0]


def test_tax_summary_pagination(client):
    r = client.get("/tax-summary?group_by=housing_type&limit=2", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()["results"]) <= 2


def test_tax_summary_invalid_group_by_is_422(client):
    r = client.get("/tax-summary?group_by=banana", headers=HEADERS)
    assert r.status_code == 422  # fails enum validation


def test_taxpayer_found(client):
    r = client.get("/taxpayers/SG001", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["profile"]["taxpayer_id"] == "SG001"
    assert len(r.json()["returns"]) >= 1


def test_taxpayer_not_found_is_404(client):
    r = client.get("/taxpayers/SG999999", headers=HEADERS)
    assert r.status_code == 404
