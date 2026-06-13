"""
duckdb connection helper and schema initialisation.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    """
    open a duckdb connection (in-memory by default, or a file path).
    """
    return duckdb.connect(str(db_path))


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    """
    create the tables and sequences if they don't already exist.
    """
    con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
