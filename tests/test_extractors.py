"""
tests for csv schema-evolution handling and defensive json parsing.
"""

from __future__ import annotations

import json

import pandas as pd

from tax_pipeline.ingestion.csv_extractor import CsvBatchExtractor
from tax_pipeline.ingestion.json_extractor import HAS_ISSUES, JsonEmployerExtractor
from tax_pipeline.models import schema

DAY1_HEADER = ",".join(schema.BASE_COLUMNS)
DAY1_ROW = "SG001,S1234567A,Tan,Single,2023,2024-03-15,85000,72050,8205,8500,12950,0,Engineer,Resident,119077,HDB 4-room,17000,0,EMP001"


def test_csv_adds_incremental_columns_for_day1(tmp_path):
    # day 1 file lacks batch_date/record_type
    f = tmp_path / "day1.csv"
    f.write_text(f"{DAY1_HEADER}\n{DAY1_ROW}\n", encoding="utf-8")

    df = CsvBatchExtractor(f).extract()

    assert schema.BATCH_DATE in df.columns
    assert schema.RECORD_TYPE in df.columns
    # missing record_type defaults to the initial-load type
    assert df[schema.RECORD_TYPE].tolist() == ["new"]
    assert pd.isna(df[schema.BATCH_DATE].iloc[0])


def test_csv_preserves_leading_zero_postal_code(tmp_path):
    row = DAY1_ROW.replace("119077", "018234")
    f = tmp_path / "day1.csv"
    f.write_text(f"{DAY1_HEADER}\n{row}\n", encoding="utf-8")

    df = CsvBatchExtractor(f).extract()
    assert df[schema.POSTAL_CODE].iloc[0] == "018234"


def test_csv_ignores_unexpected_columns(tmp_path):
    header = f"{DAY1_HEADER},surprise_col"
    row = f"{DAY1_ROW},junk"
    f = tmp_path / "day1.csv"
    f.write_text(f"{header}\n{row}\n", encoding="utf-8")

    df = CsvBatchExtractor(f).extract()
    assert "surprise_col" not in df.columns  # dropped, not fatal


def test_json_handles_null_uen_and_string_count_and_extras(tmp_path):
    records = [
        {"employer_id": "EMP009", "company_name": "LogiFlow", "uen": None,
         "industry": "Logistics", "address": "X", "employee_count": 280},
        {"employer_id": "EMP016", "company_name": "MediCare", "uen": "200423456N",
         "industry": "Healthcare", "address": "Y", "employee_count": "320"},
        {"employer_id": "EMP014", "company_name": "GlobalConsult", "uen": "200812345L",
         "industry": "Consulting", "address": "Z", "employee_count": 350,
         "global_hq": "London", "subsidiary_of": "GC plc"},
    ]
    f = tmp_path / "employers.json"
    f.write_text(json.dumps(records), encoding="utf-8")

    df = JsonEmployerExtractor(f).extract()

    # null uen preserved as None and flagged
    assert df.loc[df.employer_id == "EMP009", schema.EMP_UEN].isna().all()
    # string "320" coerced to int 320
    assert df.loc[df.employer_id == "EMP016", schema.EMP_EMPLOYEE_COUNT].iloc[0] == 320
    # all three records are flagged as having schema issues
    assert df[HAS_ISSUES].sum() == 3
    # extra fields don't appear as columns
    assert "global_hq" not in df.columns
