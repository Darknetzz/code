"""Murder targets from rapportstream / incoming shots."""

from __future__ import annotations

from dataclasses import dataclass

from mafibot.config import BotProfile
from mafibot.state import GameState


@dataclass
class MurderTargetPick:
    username: str
    city: str | None = None
    reason: str = ""


def pick_report_stream_target(
    state: GameState,
    profile: BotProfile,
) -> MurderTargetPick | None:
    mode = profile.murder_mode
    if mode == "static_targets":
        return None
    entries = state.report_entries
    if not entries:
        return None

    if mode == "retaliate_only":
        for entry in entries:
            if entry.incoming_shot:
                return MurderTargetPick(
                    username=entry.username,
                    city=entry.city,
                    reason="retaliate",
                )
        return None

    for entry in entries:
        if entry.null_delay and not entry.incoming_shot:
            return MurderTargetPick(
                username=entry.username,
                city=entry.city,
                reason="null_delay_report",
            )
    for entry in entries:
        if entry.null_delay:
            return MurderTargetPick(
                username=entry.username,
                city=entry.city,
                reason="null_delay_report",
            )
    return None
