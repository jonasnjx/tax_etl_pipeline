"""
one logger setup so every module logs the same way, instead of using print.
"""

from __future__ import annotations

import logging

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """
    return a logger for a module, setting the shared format once.
    """
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        _CONFIGURED = True
    return logging.getLogger(name)
