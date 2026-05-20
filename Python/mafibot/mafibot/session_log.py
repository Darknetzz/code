"""Append-only session log persisted under the mafibot config dir."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from mafibot.config import get_config_dir

_LOG_DIR_NAME = "logs"
_LOG_FILE_NAME = "mafibot.log"
_MAX_BYTES = 2_000_000
_BACKUP_COUNT = 5
_DEFAULT_TAIL_LINES = 400

_configured = False


def get_log_dir() -> Path:
    return get_config_dir() / _LOG_DIR_NAME


def get_log_path() -> Path:
    return get_log_dir() / _LOG_FILE_NAME


def configure_session_file_logging() -> Path:
    """Attach a rotating file handler to the ``mafibot`` logger (idempotent)."""
    global _configured
    path = get_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if _configured:
        return path

    handler = RotatingFileHandler(
        path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger("mafibot")
    if root.level == logging.NOTSET:
        root.setLevel(logging.INFO)
    root.addHandler(handler)
    _configured = True
    return path


def append_ui_log_line(message: str) -> None:
    """Persist a dashboard-only line (profile saved, etc.)."""
    configure_session_file_logging()
    line = f"{datetime.now().isoformat(timespec='seconds')} UI: {message.strip()}\n"
    path = get_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def read_recent_log_lines(*, limit: int = _DEFAULT_TAIL_LINES) -> list[str]:
    path = get_log_path()
    if not path.is_file() or limit <= 0:
        return []
    with path.open(encoding="utf-8", errors="replace") as fh:
        return [line.rstrip("\n\r") for line in deque(fh, maxlen=limit)]


def clear_session_log() -> None:
    path = get_log_path()
    if path.is_file():
        path.write_text("", encoding="utf-8")
