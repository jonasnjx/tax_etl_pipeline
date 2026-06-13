"""
the six validation rules, each tagged with its dq domain.
rule-to-domain mapping:
    r1  nric present         -> completeness
    r2  nric format          -> validity
    r3  postal code 6-digit  -> validity
    r4  filing date after ay -> validity
    r5  chargeable = income - reliefs -> accuracy
    r6  cpf mandatory: resident       -> accuracy
"""

from __future__ import annotations

import pandas as pd

from tax_pipeline.models import schema
from tax_pipeline.models.schema import DQDomain
from tax_pipeline.validation.rule import ValidationRule

# defaults, overridable via config in build_rules
DEFAULT_NRIC_PATTERN = r"^[STFG][0-9]{7}[A-Z]$"
DEFAULT_POSTAL_PATTERN = r"^[0-9]{6}$"
DEFAULT_CPF_REQUIRED_STATUS = "Resident"


def _as_str(series: pd.Series) -> pd.Series:
    """
    blank-safe string view: na -> '' so regex/strip never produces na.
    """
    return series.fillna("").astype(str).str.strip()


class Rule1NricPresent(ValidationRule):
    rule_id = "rule1_nric_present"
    description = "NRIC is present (mandatory field)"
    domain = DQDomain.COMPLETENESS

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        return _as_str(df[schema.NRIC]) != ""


class Rule2NricFormat(ValidationRule):
    rule_id = "rule2_nric_format"
    description = "NRIC format: [STFG]xxxxxxx[A-Z]"
    domain = DQDomain.VALIDITY

    def __init__(self, pattern: str = DEFAULT_NRIC_PATTERN) -> None:
        self.pattern = pattern

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        return _as_str(df[schema.NRIC]).str.match(self.pattern)


class Rule3PostalCode(ValidationRule):
    rule_id = "rule3_postal_code"
    description = "Postal code: 6-digit numeric format"
    domain = DQDomain.VALIDITY

    def __init__(self, pattern: str = DEFAULT_POSTAL_PATTERN) -> None:
        self.pattern = pattern

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        return _as_str(df[schema.POSTAL_CODE]).str.match(self.pattern)


class Rule4FilingDateAfterAy(ValidationRule):
    rule_id = "rule4_filing_date_after_ay"
    description = "Filing date must be a real date after the assessment year"
    domain = DQDomain.VALIDITY

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        filed = pd.to_datetime(df[schema.FILING_DATE], format="%Y-%m-%d", errors="coerce")
        assessment_year = pd.to_numeric(df[schema.ASSESSMENT_YEAR], errors="coerce")
        return filed.notna() & (filed.dt.year > assessment_year)


class Rule5ChargeableIncome(ValidationRule):
    rule_id = "rule5_chargeable_income"
    description = "chargeable_income = annual_income - total_reliefs"
    domain = DQDomain.ACCURACY

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        annual = pd.to_numeric(df[schema.ANNUAL_INCOME_SGD], errors="coerce")
        reliefs = pd.to_numeric(df[schema.TOTAL_RELIEFS_SGD], errors="coerce")
        chargeable = pd.to_numeric(df[schema.CHARGEABLE_INCOME_SGD], errors="coerce")
        computable = annual.notna() & reliefs.notna() & chargeable.notna()
        # if inputs can't be computed, the row fails accuracy (can't verify)
        return computable & (chargeable == (annual - reliefs))


class Rule6CpfResident(ValidationRule):
    rule_id = "rule6_cpf_resident"
    description = "CPF contributions mandatory for Residents"
    domain = DQDomain.ACCURACY

    def __init__(self, required_status: str = DEFAULT_CPF_REQUIRED_STATUS) -> None:
        self.required_status = required_status

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        cpf = pd.to_numeric(df[schema.CPF_CONTRIBUTIONS_SGD], errors="coerce")
        is_resident = df[schema.RESIDENTIAL_STATUS] == self.required_status
        # residents need cpf > 0; non-residents exempt
        return (~is_resident) | (cpf > 0)


def build_rules(validation_config: dict[str, str] | None = None) -> list[ValidationRule]:
    """
    build the rule set, injecting patterns/params from config when provided.
    """
    cfg = validation_config or {}
    return [
        Rule1NricPresent(),
        Rule2NricFormat(cfg.get("nric_pattern", DEFAULT_NRIC_PATTERN)),
        Rule3PostalCode(cfg.get("postal_pattern", DEFAULT_POSTAL_PATTERN)),
        Rule4FilingDateAfterAy(),
        Rule5ChargeableIncome(),
        Rule6CpfResident(cfg.get("cpf_required_status", DEFAULT_CPF_REQUIRED_STATUS)),
    ]


# default rule set used by tests and simple callers
ALL_RULES: list[ValidationRule] = build_rules()
