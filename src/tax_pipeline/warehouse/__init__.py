"""
warehouse layer: duckdb schema, connection, and the dimensional loader.
"""

from tax_pipeline.warehouse.connection import get_connection, init_schema
from tax_pipeline.warehouse.loader import WarehouseLoader

__all__ = ["get_connection", "init_schema", "WarehouseLoader"]
