"""Append-only logs under the mafibot config dir (global + per autopilot session)."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from mafibot.config import get_config_dir

_LOG_DIR_NAME = "logs"
_SESSIONS_SUBDIR = "sessions"
_LOG_FILE_NAME = "mafibot.log"
_MAX_BYTES = 2_000_000
_BACKUP_COUNT = 5
_DEFAULT_TAIL_LINES = 400

_configured = False
_session_handler: logging.FileHandler | None = None
_active_session_log_path: Path | None = None
_active_session_log_id: str | None = None


def get_log_dir() -> Path:
    return get_config_dir() / _LOG_DIR_NAME


def get_sessions_log_dir() -> Path:
    return get_log_dir() / _SESSIONS_SUBDIR


def get_log_path() -> Path:
    return get_log_dir() / _LOG_FILE_NAME


def get_active_session_log_path() -> Path | None:
    return _active_session_log_path


def get_active_session_log_id() -> str | None:
    return _active_session_log_id


def _safe_session_stem(profile: str, started_at: str) -> str:
    safe_profile = re.sub(r"[^\w\-]+", "_", profile.strip())[:40] or "profile"
    safe_time = re.sub(r"[^\d\-_]+", "_", started_at.strip())[:32] or "session"
    return f"{safe_time}_{safe_profile}"


def session_log_id_from_path(path: Path) -> str:
    return path.stem


def session_log_path_from_id(session_id: str) -> Path:
    name = session_id if session_id.endswith(".log") else f"{session_id}.log"
    return get_sessions_log_dir() / name


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


def start_session_log(profile: str, started_at: str) -> Path:
    """Open a dedicated log file for one autopilot session."""
    global _session_handler, _active_session_log_path, _active_session_log_id
    configure_session_file_logging()
    end_session_log()

    sessions_dir = get_sessions_log_dir()
    sessions_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_session_stem(profile, started_at)
    path = sessions_dir / f"{stem}.log"
    if path.exists():
        n = 2
        while path.exists():
            path = sessions_dir / f"{stem}_{n}.log"
            n += 1

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger("mafibot").addHandler(handler)
    _session_handler = handler
    _active_session_log_path = path
    _active_session_log_id = path.stem

    log_session_event(
        "SESSION",
        profile=profile,
        started_at=started_at,
        log_file=str(path),
    )
    return path


def end_session_log() -> None:
    """Detach the per-session file handler."""
    global _session_handler, _active_session_log_path, _active_session_log_id
    if _session_handler is not None:
        root = logging.getLogger("mafibot")
        root.removeHandler(_session_handler)
        _session_handler.close()
        _session_handler = None
    _active_session_log_path = None
    _active_session_log_id = None


def log_session_event(kind: str, **fields: str | int | float | bool | None) -> None:
    """Append a structured line to the active session log (if any)."""
    path = _active_session_log_path
    if path is None:
        return
    parts: list[str] = [kind.upper()]
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value).replace("\n", " ").strip()
        if " " in text:
            text = f'"{text}"'
        parts.append(f"{key}={text}")
    line = f"{datetime.now().isoformat(timespec='seconds')} " + " ".join(parts) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def append_ui_log_line(message: str) -> None:
    """Persist a dashboard-only line (profile saved, etc.)."""
    configure_session_file_logging()
    line = f"{datetime.now().isoformat(timespec='seconds')} UI: {message.strip()}\n"
    path = get_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def read_log_lines(path: Path, *, limit: int = _DEFAULT_TAIL_LINES) -> list[str]:
    if not path.is_file() or limit <= 0:
        return []
    with path.open(encoding="utf-8", errors="replace") as fh:
        return [line.rstrip("\n\r") for line in deque(fh, maxlen=limit)]


def read_recent_log_lines(*, limit: int = _DEFAULT_TAIL_LINES) -> list[str]:
    active = _active_session_log_path
    if active is not None and active.is_file():
        return read_log_lines(active, limit=limit)
    return read_log_lines(get_log_path(), limit=limit)


def resolve_log_path_for_read(session_id: str | None = None) -> Path:
    if session_id:
        return session_log_path_from_id(session_id)
    active = _active_session_log_path
    if active is not None:
        return active
    return get_log_path()


@dataclass
class SessionLogInfo:
    id: str
    path: str
    profile: str
    started_at: str
    size_bytes: int
    modified_at: str


def _parse_session_log_meta(path: Path) -> tuple[str, str]:
    stem = path.stem
    parts = stem.split("_", 2)
    if len(parts) >= 3:
        date_part = parts[0]
        time_part = parts[1].replace("-", ":")
        profile = parts[2]
        started = f"{date_part} {time_part}"
        return profile, started
    return stem, ""


def list_session_logs(*, limit: int = 50) -> list[SessionLogInfo]:
    sessions_dir = get_sessions_log_dir()
    if not sessions_dir.is_dir():
        return []
    files = sorted(
        sessions_dir.glob("*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[: max(1, limit)]
    out: list[SessionLogInfo] = []
    for path in files:
        st = path.stat()
        profile, started = _parse_session_log_meta(path)
        out.append(
            SessionLogInfo(
                id=path.stem,
                path=str(path),
                profile=profile,
                started_at=started,
                size_bytes=st.st_size,
                modified_at=datetime.fromtimestamp(st.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            )
        )
    return out


def clear_session_log() -> None:
    path = resolve_log_path_for_read()
    if path.is_file():
        path.write_text("", encoding="utf-8")


def open_log_in_default_app(session_id: str | None = None) -> Path:
    """Open a log file in the OS default editor/viewer."""
    configure_session_file_logging()
    path = resolve_log_path_for_read(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.touch()
    if sys.platform == "win32":
        import os

        os.startfile(path)  # type: ignore[attr-defined,no-untyped-call]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
    return path
