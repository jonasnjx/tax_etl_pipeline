"""
compute per-domain data-quality scores from validated data.
score = (passing rows / total rows) * 100 for each domain. a row is "passing"
for a domain when it passes all rules in that domain, which the validator has
already collapsed into one boolean column per domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from tax_pipeline.models.schema import DQDomain
from tax_pipeline.validation.validator import domain_flag_column


@dataclass
class DQScore:
    """
    scoring result: per-domain percentages plus the underlying counts.
    """

    total_rows: int
    scores: dict[str, float] = field(default_factory=dict)
    passing_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "scores": self.scores,
            "passing_counts": self.passing_counts,
        }


class DQScorer:
    """
    aggregate validated rows into per-domain quality scores.
    """

    def __init__(self, domains: list[DQDomain] | None = None) -> None:
        self.domains = domains if domains is not None else list(DQDomain)

    def score(self, validated_df: pd.DataFrame) -> DQScore:
        total = len(validated_df)
        result = DQScore(total_rows=total)

        for domain in self.domains:
            col = domain_flag_column(domain)
            if col not in validated_df.columns:
                continue
            passing = int(validated_df[col].sum())
            result.passing_counts[domain.value] = passing
            result.scores[domain.value] = round(passing / total * 100, 2) if total else 0.0

        return result
