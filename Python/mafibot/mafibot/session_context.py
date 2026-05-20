"""Per-session mutable state (cancel, parse errors, dry-run log)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class DryRunDecision:
    action: str | None
    reason: str
    hotel_steps: str = ""

    def to_dict(self) -> dict[str, str | None]:
        return {
            "action": self.action,
            "reason": self.reason,
            "hotel_steps": self.hotel_steps or None,
        }


@dataclass
class SessionContext:
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    hotel_disabled_for_session: bool = False
    last_idle_detail: str | None = None
    last_parse_error: dict[str, str | None] | None = None
    dry_run_decisions: list[DryRunDecision] = field(default_factory=list)

    def request_stop(self) -> None:
        self.cancel.set()

    def clear_stop(self) -> None:
        self.cancel.clear()
        self.hotel_disabled_for_session = False
        self.last_idle_detail = None
        self.last_parse_error = None
        self.dry_run_decisions.clear()

    def is_stop_requested(self) -> bool:
        return self.cancel.is_set()

    def record_dry_run(self, action: str | None, reason: str, *, hotel_steps: str = "") -> None:
        self.dry_run_decisions.append(
            DryRunDecision(action=action, reason=reason, hotel_steps=hotel_steps)
        )
        if len(self.dry_run_decisions) > 500:
            self.dry_run_decisions = self.dry_run_decisions[-500:]
