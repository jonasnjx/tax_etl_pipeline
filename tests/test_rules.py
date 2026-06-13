"""
unit tests for the six validation rules.
fixtures use the real garbage patterns found in the data (invalid_nric,
2024-13-45, abc123, off-by-1000 incomes) so tests mirror real data.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tax_pipeline.models import schema
from tax_pipeline.validation.rules import (
    Rule1NricPresent,
    Rule2NricFormat,
    Rule3PostalCode,
    Rule4FilingDateAfterAy,
    Rule5ChargeableIncome,
    Rule6CpfResident,
)


def _df(rows: list[dict]) -> pd.DataFrame:
    """
    build a dataframe with all canonical columns (missing -> na).
    """
    frame = pd.DataFrame(rows)
    for col in schema.CANONICAL_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    return frame


# --- Rule 1: NRIC present ----------------------------------------------------------

def test_rule1_passes_when_nric_present():
    df = _df([{schema.NRIC: "S1234567A"}])
    assert Rule1NricPresent().evaluate(df).tolist() == [True]


@pytest.mark.parametrize("value", [None, "", "   "])
def test_rule1_fails_when_nric_blank(value):
    df = _df([{schema.NRIC: value}])
    assert Rule1NricPresent().evaluate(df).tolist() == [False]


# --- Rule 2: NRIC format -----------------------------------------------------------

@pytest.mark.parametrize("value", ["S1234567A", "T0123459E", "G9012348D"])
def test_rule2_passes_valid_format(value):
    df = _df([{schema.NRIC: value}])
    assert Rule2NricFormat().evaluate(df).tolist() == [True]


@pytest.mark.parametrize("value", ["INVALID_NRIC", "XXXXX1234", "S123456A", "1234567AA", ""])
def test_rule2_fails_malformed(value):
    df = _df([{schema.NRIC: value}])
    assert Rule2NricFormat().evaluate(df).tolist() == [False]


# --- Rule 3: postal code -----------------------------------------------------------

@pytest.mark.parametrize("value", ["018234", "730234", "119077"])
def test_rule3_passes_six_digits(value):
    df = _df([{schema.POSTAL_CODE: value}])
    assert Rule3PostalCode().evaluate(df).tolist() == [True]


@pytest.mark.parametrize("value", ["ABC123", "BADCODE", "12345", "1234567", ""])
def test_rule3_fails_invalid(value):
    df = _df([{schema.POSTAL_CODE: value}])
    assert Rule3PostalCode().evaluate(df).tolist() == [False]


# --- Rule 4: filing date after assessment year -------------------------------------

def test_rule4_passes_when_after_assessment_year():
    df = _df([{schema.FILING_DATE: "2024-03-15", schema.ASSESSMENT_YEAR: "2023"}])
    assert Rule4FilingDateAfterAy().evaluate(df).tolist() == [True]


@pytest.mark.parametrize("value", ["2024-13-45", "2024-02-30", "invalid-date", "bad-date", ""])
def test_rule4_fails_unparseable_dates(value):
    df = _df([{schema.FILING_DATE: value, schema.ASSESSMENT_YEAR: "2023"}])
    assert Rule4FilingDateAfterAy().evaluate(df).tolist() == [False]


def test_rule4_fails_when_not_after_assessment_year():
    # filed in 2023 for assessment year 2023, not strictly after
    df = _df([{schema.FILING_DATE: "2023-06-01", schema.ASSESSMENT_YEAR: "2023"}])
    assert Rule4FilingDateAfterAy().evaluate(df).tolist() == [False]


# --- Rule 5: chargeable income accuracy --------------------------------------------

def test_rule5_passes_when_math_holds():
    df = _df([{
        schema.ANNUAL_INCOME_SGD: "85000",
        schema.TOTAL_RELIEFS_SGD: "12950",
        schema.CHARGEABLE_INCOME_SGD: "72050",
    }])
    assert Rule5ChargeableIncome().evaluate(df).tolist() == [True]


def test_rule5_fails_off_by_1000():
    df = _df([{
        schema.ANNUAL_INCOME_SGD: "49000",
        schema.TOTAL_RELIEFS_SGD: "6000",
        schema.CHARGEABLE_INCOME_SGD: "42000",  # should be 43000
    }])
    assert Rule5ChargeableIncome().evaluate(df).tolist() == [False]


def test_rule5_fails_when_input_missing():
    df = _df([{
        schema.ANNUAL_INCOME_SGD: "",
        schema.TOTAL_RELIEFS_SGD: "6000",
        schema.CHARGEABLE_INCOME_SGD: "42000",
    }])
    assert Rule5ChargeableIncome().evaluate(df).tolist() == [False]


# --- Rule 6: CPF mandatory for residents -------------------------------------------

def test_rule6_passes_resident_with_cpf():
    df = _df([{schema.RESIDENTIAL_STATUS: "Resident", schema.CPF_CONTRIBUTIONS_SGD: "17000"}])
    assert Rule6CpfResident().evaluate(df).tolist() == [True]


def test_rule6_fails_resident_without_cpf():
    df = _df([{schema.RESIDENTIAL_STATUS: "Resident", schema.CPF_CONTRIBUTIONS_SGD: "0"}])
    assert Rule6CpfResident().evaluate(df).tolist() == [False]


def test_rule6_passes_non_resident_without_cpf():
    df = _df([{schema.RESIDENTIAL_STATUS: "Non-Resident", schema.CPF_CONTRIBUTIONS_SGD: "0"}])
    assert Rule6CpfResident().evaluate(df).tolist() == [True]
