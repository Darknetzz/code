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
    hotel_skip_insufficient_funds: int = 0
    hotel_skip_hotel_full: int = 0
    hotel_skip_wallet_low: int = 0
    samples_in_hotel: int = 0
    samples_out_hotel: int = 0
    money_start: int | None = None
    money_end: int | None = None
    rank_start: int | None = None
    rank_end: int | None = None
    stop_reason: str | None = None
    action_counts: dict[str, int] = field(default_factory=dict)

    def record_action(self, name: str) -> None:
        """Increment counter for a successfully completed action."""
        self.action_counts[name] = self.action_counts.get(name, 0) + 1

    def record_hotel_sample(self, in_hotel: bool) -> None:
        if in_hotel:
            self.samples_in_hotel += 1
        else:
            self.samples_out_hotel += 1

    def record_hotel_skip(self, reason: str) -> None:
        if reason == "insufficient_funds":
            self.hotel_skip_insufficient_funds += 1
        elif reason == "hotel_full":
            self.hotel_skip_hotel_full += 1
        elif reason in ("wallet_low", "hotel_min_wallet"):
            self.hotel_skip_wallet_low += 1

    @property
    def hotel_time_percent(self) -> float | None:
        total = self.samples_in_hotel + self.samples_out_hotel
        if not total:
            return None
        return 100.0 * self.samples_in_hotel / total

    @property
    def rank_points_gained(self) -> int | None:
        if self.rank_start is None or self.rank_end is None:
            return None
        return self.rank_end - self.rank_start

    def to_dict(self) -> dict:
        data = asdict(self)
        data["hotel_time_percent"] = self.hotel_time_percent
        data["rank_points_gained"] = self.rank_points_gained
        return data

    @classmethod
    def from_dict(cls, data: dict) -> SessionMetrics:
        fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in fields})


_metrics: SessionMetrics | None = None


def _sessions_history_path() -> Path:
    return get_config_dir() / "sessions_history.ndjson"


def append_session_history(metrics: SessionMetrics) -> None:
    path = _sessions_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(metrics.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load_session_history(*, limit: int = 50) -> list[SessionMetrics]:
    path = _sessions_history_path()
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    out: list[SessionMetrics] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(SessionMetrics.from_dict(json.loads(line)))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return list(reversed(out))


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
    append_session_history(_metrics)
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
