"""
employer json extractor with defensive, per-record parsing.
the source has intentional issues: missing fields (uen: null), type mismatches
(employee_count as "320"), and extra fields (global_hq, subsidiary_of). each
record is parsed independently with defaults and best-effort coercion. a bad
record is flagged, never fatal, so one bad employer can't fail the load.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tax_pipeline.ingestion.base_extractor import BaseExtractor
from tax_pipeline.models import schema
from tax_pipeline.utils.logging import get_logger

logger = get_logger(__name__)

# flag column marking records that had a missing/invalid required field
HAS_ISSUES = "has_schema_issues"
ISSUE_DETAIL = "schema_issue_detail"


class JsonEmployerExtractor(BaseExtractor):
    """
    extract employer reference data into a stable canonical schema.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def extract(self) -> pd.DataFrame:
        logger.info("Extracting employer JSON: %s", self.path.name)
        with open(self.path, encoding="utf-8") as fh:
            raw_records = json.load(fh)

        parsed = [self._parse_record(rec, idx) for idx, rec in enumerate(raw_records)]
        df = pd.DataFrame(parsed)

        n_issues = int(df[HAS_ISSUES].sum())
        logger.info("Extracted %d employers (%d with schema issues)", len(df), n_issues)
        return df

    def _parse_record(self, record: dict, idx: int) -> dict:
        """
        coerce one raw employer dict into the canonical shape, collecting issues.
        """
        issues: list[str] = []

        employer_id = record.get(schema.EMP_ID)
        if not employer_id:
            issues.append("missing employer_id")
            employer_id = f"UNKNOWN_{idx}"

        uen = record.get(schema.EMP_UEN)
        if uen in (None, ""):
            issues.append("missing uen")
            uen = None

        employee_count = self._coerce_int(record.get(schema.EMP_EMPLOYEE_COUNT), issues)

        # capture unexpected fields without letting them break the schema
        extras = set(record) - set(schema.EMPLOYER_COLUMNS)
        if extras:
            issues.append(f"extra fields: {sorted(extras)}")

        return {
            schema.EMP_ID: employer_id,
            schema.EMP_COMPANY_NAME: record.get(schema.EMP_COMPANY_NAME),
            schema.EMP_UEN: uen,
            schema.EMP_INDUSTRY: record.get(schema.EMP_INDUSTRY),
            schema.EMP_ADDRESS: record.get(schema.EMP_ADDRESS),
            schema.EMP_EMPLOYEE_COUNT: employee_count,
            HAS_ISSUES: bool(issues),
            ISSUE_DETAIL: "; ".join(issues) if issues else None,
        }

    @staticmethod
    def _coerce_int(value: object, issues: list[str]) -> int | None:
        """
        coerce a possibly string/none employee_count to int, flagging mismatches.
        """
        if value is None:
            issues.append("missing employee_count")
            return None
        if isinstance(value, bool):  # guard: bool is an int subclass
            issues.append("invalid employee_count type")
            return None
        if isinstance(value, int):
            return value
        try:
            coerced = int(str(value).strip())
            issues.append("employee_count was non-integer; coerced")
            return coerced
        except (ValueError, TypeError):
            issues.append("uncoercible employee_count")
            return None
