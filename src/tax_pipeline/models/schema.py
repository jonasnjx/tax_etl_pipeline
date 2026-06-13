"""
shared schema: one place listing every column name and allowed value.
main purpose: rename a column here once, instead of across every file.
also makes the day 2/3 schema evolution explicit.
"""

from __future__ import annotations

from enum import Enum


class DQDomain(str, Enum):
    """
    the three data-quality domains we score.
    """

    COMPLETENESS = "completeness"
    VALIDITY = "validity"
    ACCURACY = "accuracy"


# individual tax-return columns
TAXPAYER_ID = "taxpayer_id"
NRIC = "nric"
FULL_NAME = "full_name"
FILING_STATUS = "filing_status"
ASSESSMENT_YEAR = "assessment_year"
FILING_DATE = "filing_date"
ANNUAL_INCOME_SGD = "annual_income_sgd"
CHARGEABLE_INCOME_SGD = "chargeable_income_sgd"
TAX_PAYABLE_SGD = "tax_payable_sgd"
TAX_PAID_SGD = "tax_paid_sgd"
TOTAL_RELIEFS_SGD = "total_reliefs_sgd"
NUMBER_OF_DEPENDENTS = "number_of_dependents"
OCCUPATION = "occupation"
RESIDENTIAL_STATUS = "residential_status"
POSTAL_CODE = "postal_code"
HOUSING_TYPE = "housing_type"
CPF_CONTRIBUTIONS_SGD = "cpf_contributions_sgd"
FOREIGN_INCOME_SGD = "foreign_income_sgd"
EMPLOYER_ID = "employer_id"
BATCH_DATE = "batch_date"
RECORD_TYPE = "record_type"

# base columns present in every batch (day 1's 19 columns)
BASE_COLUMNS: list[str] = [
    TAXPAYER_ID, NRIC, FULL_NAME, FILING_STATUS, ASSESSMENT_YEAR, FILING_DATE,
    ANNUAL_INCOME_SGD, CHARGEABLE_INCOME_SGD, TAX_PAYABLE_SGD, TAX_PAID_SGD, TOTAL_RELIEFS_SGD,
    NUMBER_OF_DEPENDENTS, OCCUPATION, RESIDENTIAL_STATUS, POSTAL_CODE, HOUSING_TYPE,
    CPF_CONTRIBUTIONS_SGD, FOREIGN_INCOME_SGD, EMPLOYER_ID,
]

# columns added by the day 2/3 schema evolution
INCREMENTAL_COLUMNS: list[str] = [BATCH_DATE, RECORD_TYPE]

# the full canonical individual schema every batch is normalised to
CANONICAL_COLUMNS: list[str] = BASE_COLUMNS + INCREMENTAL_COLUMNS


# employer columns
EMP_ID = "employer_id"
EMP_COMPANY_NAME = "company_name"
EMP_UEN = "uen"
EMP_INDUSTRY = "industry"
EMP_ADDRESS = "address"
EMP_EMPLOYEE_COUNT = "employee_count"

EMPLOYER_COLUMNS: list[str] = [
    EMP_ID, EMP_COMPANY_NAME, EMP_UEN, EMP_INDUSTRY, EMP_ADDRESS, EMP_EMPLOYEE_COUNT,
]
