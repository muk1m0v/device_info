"""Minimal rotating file logger.

Writes to logs/device-info.log (git-ignored), 256 KB per file, 2 backups.
Only lifecycle events are logged; device serials are truncated and no
secrets are ever logged (this project stores none).
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "device-info.log"

_configured = False


def get_logger(name: str = "device_info") -> logging.Logger:
    """Return the project logger, configuring the file handler once."""
    global _configured
    logger = logging.getLogger(name)
    if _configured:
        return logger
    logger.setLevel(logging.INFO)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            LOG_FILE, maxBytes=256 * 1024, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    except OSError:
        # Logging must never break the app (read-only media, permissions…).
        logger.addHandler(logging.NullHandler())
    logger.propagate = False
    _configured = True
    return logger


def short_serial(serial: str) -> str:
    """Truncate a serial for logs: first 4 chars + *** (privacy)."""
    if not serial:
        return "-"
    return f"{serial[:4]}***"
