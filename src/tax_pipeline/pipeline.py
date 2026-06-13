"""
entry point: wire extraction -> validation -> dq scoring together.
intentionally thin: each stage is an independent, testable component.
persistence and dimensional loading come later; here we just produce a
validated, flagged dataframe and the per-domain scores.
"""

from __future__ import annotations

import pandas as pd

from tax_pipeline.config import Config
from tax_pipeline.ingestion import CsvBatchExtractor, JsonEmployerExtractor
from tax_pipeline.quality import DQScore, DQScorer
from tax_pipeline.validation import Validator, build_rules
from tax_pipeline.utils.logging import get_logger

logger = get_logger(__name__)


class IngestionPipeline:
    """
    run the ingestion and data-quality stage across all configured batches.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        self.validator = Validator(build_rules(self.config.validation))
        self.scorer = DQScorer()

    def run_individual(self) -> tuple[pd.DataFrame, DQScore]:
        """
        extract all daily batches, validate, and score data quality.
        """
        frames = []
        for path in self.config.individual_files():
            frames.append(CsvBatchExtractor(path).extract())

        combined = pd.concat(frames, ignore_index=True)
        validated = self.validator.validate(combined)
        score = self.scorer.score(validated)
        logger.info("Data quality scores: %s", score.scores)
        return validated, score

    def run_employers(self) -> pd.DataFrame:
        """
        extract employer reference data (defensive parse, no scoring).
        """
        extractor = JsonEmployerExtractor(self.config.resolve(self.config.employer_json))
        return extractor.extract()


def main() -> None:
    pipeline = IngestionPipeline()
    validated, score = pipeline.run_individual()
    employers = pipeline.run_employers()

    print("\n=== Ingestion & Data Quality ===")
    print(f"Individual rows ingested : {len(validated)}")
    print(f"Employers ingested       : {len(employers)}")
    print(f"Total rows scored        : {score.total_rows}")
    print("\nData Quality Scores (per domain):")
    for domain, value in score.scores.items():
        passing = score.passing_counts[domain]
        print(f"  {domain:13}: {value:6.2f}%  ({passing}/{score.total_rows} rows pass)")


if __name__ == "__main__":
    main()
