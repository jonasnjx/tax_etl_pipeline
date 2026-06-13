"""
loads the yaml config file so the rest of the code can read settings from it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# project root is two levels up from this file (src/tax_pipeline/config.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "pipeline.yml"


class Config:
    """
    reads values from the parsed yaml and resolves paths to absolute.
    """

    def __init__(self, raw: dict[str, Any], root: Path = PROJECT_ROOT) -> None:
        self._raw = raw
        self._root = root

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "Config":
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        return cls(raw)

    def resolve(self, relative_path: str) -> Path:
        """
        turn a config-relative path into an absolute path under the project root.
        """
        return self._root / relative_path

    def individual_files(self) -> list[Path]:
        """
        find all batch csvs in the configured folder, sorted by filename.
        sorted order (day1, day2, day3) matters for sequential loading later.
        """
        directory = self.resolve(self._raw["data"]["individual_dir"])
        pattern = self._raw["data"]["individual_pattern"]
        return sorted(directory.glob(pattern))

    @property
    def employer_json(self) -> str:
        return self._raw["data"]["employer_json"]

    @property
    def validation(self) -> dict[str, str]:
        return self._raw["validation"]

    @property
    def orchestration(self) -> dict:
        return self._raw.get("orchestration", {})

    @property
    def api(self) -> dict:
        return self._raw.get("api", {})
