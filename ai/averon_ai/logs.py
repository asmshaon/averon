"""Structured key=value logging to stderr. Never pass audio, transcription or translation text here."""

from __future__ import annotations

import logging
import os
import sys

_logger = logging.getLogger("averon_ai")


def configure(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose or os.environ.get("AVERON_LOG_LEVEL", "").upper() == "DEBUG" else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s level=%(levelname)s %(message)s"))
    _logger.handlers[:] = [handler]
    _logger.setLevel(level)
    _logger.propagate = False


def event(name: str, level: int = logging.INFO, **fields: object) -> None:
    """Log an event. Values must be IDs, codes, numbers or model names: never user content."""
    parts = [f"event={name}"] + [f"{k}={v}" for k, v in fields.items() if v is not None]
    _logger.log(level, " ".join(parts))
