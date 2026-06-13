"""
abstract base class defining the extractor contract.
every source (csv batch, employer json, a future api) implements the same
extract() interface, so downstream code is decoupled from the source format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseExtractor(ABC):
    """
    contract for all source extractors.
    """

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """
        read the source and return a dataframe normalised to a canonical schema.
        implementations must not raise on bad records; they should coerce/flag
        and keep going so one bad row never fails the whole batch.
        """
        raise NotImplementedError
