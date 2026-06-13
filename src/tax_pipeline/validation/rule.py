"""
abstract validation rule.
each rule carries its own dq-domain tag, which gives a clear rule-to-domain
mapping: scoring groups rules by rule.domain automatically, with no separate
lookup table to maintain. rules are vectorised: evaluate returns a boolean
series over the whole dataframe (true = the row passes).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from tax_pipeline.models.schema import DQDomain


class ValidationRule(ABC):
    """
    base class for a single validation rule.
    """

    #: Stable identifier, e.g. "rule1_nric_present". Used for flag column names.
    rule_id: str
    #: human-readable description of the rule
    description: str
    #: The data-quality domain this rule contributes to.
    domain: DQDomain

    @abstractmethod
    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        """
        return a boolean series aligned to df.index; true means the row passes.
        """
        raise NotImplementedError

    @property
    def flag_column(self) -> str:
        """
        per-record flag column name produced for this rule.
        """
        return f"dq_{self.rule_id}_pass"
