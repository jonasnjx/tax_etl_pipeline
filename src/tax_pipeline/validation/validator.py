"""
applies rules and adds per-record and per-domain pass flags.
for each row it adds one boolean column per rule (e.g. dq_rule2_nric_format_pass)
and one per domain (e.g. dq_validity_pass). a row passes a domain only if it
passes all rules in that domain, so the domain flag is the logical and of them.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from tax_pipeline.models.schema import DQDomain
from tax_pipeline.validation.rule import ValidationRule
from tax_pipeline.validation.rules import ALL_RULES
from tax_pipeline.utils.logging import get_logger

logger = get_logger(__name__)


def domain_flag_column(domain: DQDomain) -> str:
    return f"dq_{domain.value}_pass"


class Validator:
    """
    run a set of validation rules over a dataframe and append dq flags.
    """

    def __init__(self, rules: list[ValidationRule] | None = None) -> None:
        self.rules = rules if rules is not None else ALL_RULES

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        return a copy of df with per-rule and per-domain pass flags appended.
        """
        result = df.copy()
        domain_to_flags: dict[DQDomain, list[str]] = defaultdict(list)

        for rule in self.rules:
            flags = rule.evaluate(df).fillna(False).astype(bool)
            result[rule.flag_column] = flags
            domain_to_flags[rule.domain].append(rule.flag_column)

        # a domain passes only if every rule in it passes (logical and)
        for domain, flag_cols in domain_to_flags.items():
            result[domain_flag_column(domain)] = result[flag_cols].all(axis=1)

        logger.info("Validated %d rows against %d rules", len(result), len(self.rules))
        return result
