"""
ingestion layer: source extractors for csv batches and employer json.
"""

from tax_pipeline.ingestion.csv_extractor import CsvBatchExtractor
from tax_pipeline.ingestion.json_extractor import JsonEmployerExtractor

__all__ = ["CsvBatchExtractor", "JsonEmployerExtractor"]
