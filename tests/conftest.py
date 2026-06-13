"""
shared pytest setup. runs prefect flows against a temporary local test backend
so tests don't spin up a server per run (faster, and no shutdown log noise).
"""

from __future__ import annotations

import pytest
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session", autouse=True)
def prefect_test_backend():
    with prefect_test_harness():
        yield
