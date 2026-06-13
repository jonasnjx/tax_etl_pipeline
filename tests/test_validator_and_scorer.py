"""
tests for domain roll-up (validator) and dq scoring (dqscorer).
"""

from __future__ import annotations

import pandas as pd

from tax_pipeline.models import schema
from tax_pipeline.models.schema import DQDomain
from tax_pipeline.quality.scorer import DQScorer
from tax_pipeline.validation.validator import Validator, domain_flag_column


def _df(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for col in schema.CANONICAL_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    return frame


CLEAN_ROW = {
    schema.NRIC: "S1234567A",
    schema.ASSESSMENT_YEAR: "2023",
    schema.FILING_DATE: "2024-03-15",
    schema.ANNUAL_INCOME_SGD: "85000",
    schema.TOTAL_RELIEFS_SGD: "12950",
    schema.CHARGEABLE_INCOME_SGD: "72050",
    schema.RESIDENTIAL_STATUS: "Resident",
    schema.CPF_CONTRIBUTIONS_SGD: "17000",
    schema.POSTAL_CODE: "119077",
}


def test_validator_adds_per_rule_and_per_domain_flags():
    validated = Validator().validate(_df([CLEAN_ROW]))
    # all three domain flags present and true for a clean row
    for domain in DQDomain:
        assert validated[domain_flag_column(domain)].tolist() == [True]


def test_domain_fails_if_any_rule_in_it_fails():
    # break only the postal code (a validity rule); validity must fail while
    # completeness and accuracy still pass
    row = {**CLEAN_ROW, schema.POSTAL_CODE: "ABC123"}
    validated = Validator().validate(_df([row]))
    assert validated[domain_flag_column(DQDomain.VALIDITY)].tolist() == [False]
    assert validated[domain_flag_column(DQDomain.COMPLETENESS)].tolist() == [True]
    assert validated[domain_flag_column(DQDomain.ACCURACY)].tolist() == [True]


def test_scorer_computes_percentage_per_domain():
    # 3 clean rows + 1 with a bad postal code => Validity 75%, others 100%.
    bad = {**CLEAN_ROW, schema.POSTAL_CODE: "ABC123"}
    validated = Validator().validate(_df([CLEAN_ROW, CLEAN_ROW, CLEAN_ROW, bad]))
    score = DQScorer().score(validated)

    assert score.total_rows == 4
    assert score.scores[DQDomain.VALIDITY.value] == 75.0
    assert score.scores[DQDomain.COMPLETENESS.value] == 100.0
    assert score.scores[DQDomain.ACCURACY.value] == 100.0


def test_scorer_handles_empty_frame():
    validated = Validator().validate(_df([]))
    score = DQScorer().score(validated)
    assert score.total_rows == 0
    assert score.scores[DQDomain.VALIDITY.value] == 0.0
