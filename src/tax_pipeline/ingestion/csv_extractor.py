"""
csv batch extractor that handles schema evolution.
day 1 has 19 columns; day 2/3 add batch_date and record_type. we read by header
and normalise every batch to the canonical schema: missing columns are added,
unexpected ones are logged and dropped. fields are read as strings to preserve
leading zeros (postal codes, nric); type coercion happens in validation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tax_pipeline.ingestion.base_extractor import BaseExtractor
from tax_pipeline.models import schema
from tax_pipeline.utils.logging import get_logger

logger = get_logger(__name__)


class CsvBatchExtractor(BaseExtractor):
    """
    extract one daily csv batch into the canonical individual schema.
    """

    def __init__(self, path: str | Path, default_record_type: str = "new") -> None:
        self.path = Path(path)
        self.default_record_type = default_record_type

    def extract(self) -> pd.DataFrame:
        logger.info("Extracting CSV batch: %s", self.path.name)
        # read as strings; coerce types later in validation
        df = pd.read_csv(self.path, dtype=str, keep_default_na=False, na_values=[""])

        df = self._handle_schema_evolution(df)
        logger.info("Extracted %d rows from %s", len(df), self.path.name)
        return df[schema.CANONICAL_COLUMNS]

    def _handle_schema_evolution(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        add missing canonical columns; drop and log unexpected extras.
        """
        incoming = set(df.columns)

        # add canonical columns the batch is missing (day 1 lacks the incremental ones)
        for col in schema.CANONICAL_COLUMNS:
            if col not in incoming:
                df[col] = pd.NA
                logger.info("Added missing canonical column '%s' to %s", col, self.path.name)

        # blank record_type defaults to new
        df[schema.RECORD_TYPE] = df[schema.RECORD_TYPE].fillna(self.default_record_type)

        # tolerate columns we don't model
        extras = incoming - set(schema.CANONICAL_COLUMNS)
        if extras:
            logger.warning("Ignoring unexpected columns in %s: %s", self.path.name, sorted(extras))

        return df
