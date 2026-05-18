"""Per-session counters and summary persisted under config dir."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from mafibot.config import get_config_dir


@dataclass
class SessionMetrics:
    profile: str = ""
    started_at: str = ""
    ended_at: str = ""
    dry_run: bool = False
    actions_run: int = 0
    actions_failed: int = 0
    actions_skipped: int = 0
    parse_failures: int = 0
    hotel_book_failures: int = 0
    samples_in_hotel: int = 0
    samples_out_hotel: int = 0
    money_start: int | None = None
    money_end: int | None = None
    rank_start: int | None = None
    rank_end: int | None = None
    stop_reason: str | None = None

    def record_hotel_sample(self, in_hotel: bool) -> None:
        if in_hotel:
            self.samples_in_hotel += 1
        else:
            self.samples_out_hotel += 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SessionMetrics:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


_metrics: SessionMetrics | None = None


def start_session_metrics(profile: str, *, dry_run: bool = False) -> SessionMetrics:
    global _metrics
    _metrics = SessionMetrics(
        profile=profile,
        started_at=datetime.now().isoformat(timespec="seconds"),
        dry_run=dry_run,
    )
    return _metrics


def current_session_metrics() -> SessionMetrics | None:
    return _metrics


def finish_session_metrics(
    *,
    stop_reason: str | None = None,
    money_end: int | None = None,
    rank_end: int | None = None,
) -> SessionMetrics | None:
    global _metrics
    if _metrics is None:
        return None
    _metrics.ended_at = datetime.now().isoformat(timespec="seconds")
    _metrics.stop_reason = stop_reason
    if money_end is not None:
        _metrics.money_end = money_end
    if rank_end is not None:
        _metrics.rank_end = rank_end
    save_last_session_summary(_metrics)
    finished = _metrics
    _metrics = None
    return finished


def save_last_session_summary(metrics: SessionMetrics) -> Path:
    path = get_config_dir() / "last_session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics.to_dict(), indent=2), encoding="utf-8")
    return path


def load_last_session_summary() -> SessionMetrics | None:
    path = get_config_dir() / "last_session.json"
    if not path.is_file():
        return None
    try:
        return SessionMetrics.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
