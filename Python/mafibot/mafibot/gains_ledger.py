"""Per-session and lifetime gain/loss counters by income source."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from mafibot.config import get_config_dir

INCOME_SOURCES: tuple[str, ...] = (
    "enkel_krim",
    "tung_krim",
    "stjel",
    "organisert_krim",
    "narkotika_solgt",
    "narkotika_kjop",
    "bedrift",
    "rederi",
    "marked",
    "oppdrag",
    "bank",
    "reise",
    "drap",
    "hotel",
    "annet",
)

_CRIME_SECTION_TO_SOURCE = {
    "enkel": "enkel_krim",
    "tung": "tung_krim",
    "stjel": "stjel",
}

_ACTION_TO_SOURCE = {
    "organized_crime": "organisert_krim",
    "business": "bedrift",
    "ship": "rederi",
    "market": "marked",
    "missions": "oppdrag",
    "bank": "bank",
    "travel": "reise",
    "murder": "drap",
    "drugs": "narkotika_solgt",
    "hotel": "hotel",
    "book_hotel": "hotel",
}


def source_for_crime_section(section_id: str) -> str:
    return _CRIME_SECTION_TO_SOURCE.get(section_id, "annet")


def source_for_action(action_name: str, *, result_source: str | None = None) -> str:
    if result_source:
        return result_source
    return _ACTION_TO_SOURCE.get(action_name, "annet")


@dataclass
class ActionGainEvent:
    action: str
    source: str
    success: bool
    money_delta: int = 0
    rank_delta: int = 0
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GainsLedger:
    money_net: int = 0
    money_by_source: dict[str, int] = field(default_factory=dict)
    rank_points_net: int = 0
    rank_points_by_source: dict[str, int] = field(default_factory=dict)
    minion_skills_net: dict[str, float] = field(default_factory=dict)
    cannabis_grams_sold: int = 0
    opium_grams_sold: int = 0
    action_events: list[dict] = field(default_factory=list)
    _max_events: int = 500

    def _add_to_map(self, bucket: dict[str, int], source: str, delta: int) -> None:
        if delta == 0:
            return
        bucket[source] = bucket.get(source, 0) + delta

    def record_money(self, source: str, delta: int) -> None:
        if delta == 0:
            return
        self.money_net += delta
        self._add_to_map(self.money_by_source, source, delta)

    def record_rank(self, source: str, delta: int) -> None:
        if delta == 0:
            return
        self.rank_points_net += delta
        self._add_to_map(self.rank_points_by_source, source, delta)

    def record_minion_skill(self, skill: str, delta: float) -> None:
        if abs(delta) < 0.05:
            return
        key = skill.lower()
        self.minion_skills_net[key] = round(
            self.minion_skills_net.get(key, 0.0) + delta, 1
        )

    def record_grams_sold(self, *, cannabis: int = 0, opium: int = 0) -> None:
        if cannabis > 0:
            self.cannabis_grams_sold += cannabis
        if opium > 0:
            self.opium_grams_sold += opium

    def record_action_event(
        self,
        *,
        action: str,
        source: str,
        success: bool,
        money_delta: int = 0,
        rank_delta: int = 0,
        message: str = "",
    ) -> None:
        if money_delta:
            self.record_money(source, money_delta)
        if rank_delta:
            self.record_rank(source, rank_delta)
        event = ActionGainEvent(
            action=action,
            source=source,
            success=success,
            money_delta=money_delta,
            rank_delta=rank_delta,
            message=message[:200],
        )
        self.action_events.append(event.to_dict())
        if len(self.action_events) > self._max_events:
            self.action_events = self.action_events[-self._max_events :]

    def merge(self, other: GainsLedger) -> None:
        self.money_net += other.money_net
        for src, val in other.money_by_source.items():
            self._add_to_map(self.money_by_source, src, val)
        self.rank_points_net += other.rank_points_net
        for src, val in other.rank_points_by_source.items():
            self._add_to_map(self.rank_points_by_source, src, val)
        for skill, val in other.minion_skills_net.items():
            self.minion_skills_net[skill] = round(
                self.minion_skills_net.get(skill, 0.0) + val, 1
            )
        self.cannabis_grams_sold += other.cannabis_grams_sold
        self.opium_grams_sold += other.opium_grams_sold
        self.action_events.extend(other.action_events)
        if len(self.action_events) > self._max_events:
            self.action_events = self.action_events[-self._max_events :]

    def to_dict(self) -> dict:
        return {
            "money_net": self.money_net,
            "money_by_source": dict(self.money_by_source),
            "rank_points_net": self.rank_points_net,
            "rank_points_by_source": dict(self.rank_points_by_source),
            "minion_skills_net": dict(self.minion_skills_net),
            "cannabis_grams_sold": self.cannabis_grams_sold,
            "opium_grams_sold": self.opium_grams_sold,
            "action_events": list(self.action_events),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> GainsLedger:
        if not data:
            return cls()
        return cls(
            money_net=int(data.get("money_net") or 0),
            money_by_source={
                str(k): int(v) for k, v in (data.get("money_by_source") or {}).items()
            },
            rank_points_net=int(data.get("rank_points_net") or 0),
            rank_points_by_source={
                str(k): int(v)
                for k, v in (data.get("rank_points_by_source") or {}).items()
            },
            minion_skills_net={
                str(k): float(v)
                for k, v in (data.get("minion_skills_net") or {}).items()
            },
            cannabis_grams_sold=int(data.get("cannabis_grams_sold") or 0),
            opium_grams_sold=int(data.get("opium_grams_sold") or 0),
            action_events=list(data.get("action_events") or []),
        )


def _lifetime_path() -> Path:
    return get_config_dir() / "lifetime_stats.json"


def load_lifetime_gains() -> GainsLedger:
    path = _lifetime_path()
    if not path.is_file():
        return GainsLedger()
    try:
        return GainsLedger.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError, ValueError):
        return GainsLedger()


def save_lifetime_gains(ledger: GainsLedger) -> Path:
    path = _lifetime_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger.to_dict(), indent=2), encoding="utf-8")
    return path


def merge_session_into_lifetime(session_ledger: GainsLedger) -> GainsLedger:
    lifetime = load_lifetime_gains()
    lifetime.merge(session_ledger)
    save_lifetime_gains(lifetime)
    return lifetime
