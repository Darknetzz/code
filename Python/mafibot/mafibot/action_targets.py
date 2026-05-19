"""Murder target list helpers."""

from __future__ import annotations

from mafibot.config import BotProfile
from mafibot.report_stream import MurderTargetPick, pick_report_stream_target
from mafibot.state import GameState

_murder_rotate_index = 0
_pending_report_pick: MurderTargetPick | None = None


def reset_indices() -> None:
    global _murder_rotate_index, _pending_report_pick
    _murder_rotate_index = 0
    _pending_report_pick = None


def murder_target_names(profile: BotProfile) -> list[str]:
    return [t.strip() for t in profile.murder_targets if t and t.strip()]


def set_pending_report_pick(pick: MurderTargetPick | None) -> None:
    global _pending_report_pick
    _pending_report_pick = pick


def get_pending_report_pick() -> MurderTargetPick | None:
    return _pending_report_pick


def pick_murder_target(profile: BotProfile, state: GameState | None = None) -> str | None:
    global _murder_rotate_index, _pending_report_pick
    if state is not None and profile.murder_mode != "static_targets":
        pick = pick_report_stream_target(state, profile)
        if pick:
            _pending_report_pick = pick
            return pick.username
    if _pending_report_pick is not None:
        return _pending_report_pick.username
    names = murder_target_names(profile)
    if not names:
        return None
    if profile.murder_rotate_targets and len(names) > 1:
        name = names[_murder_rotate_index % len(names)]
        _murder_rotate_index += 1
        return name
    return names[0]


def murder_target_city(profile: BotProfile, state: GameState | None = None) -> str | None:
    if _pending_report_pick is not None:
        return _pending_report_pick.city
    if state is not None:
        pick = pick_report_stream_target(state, profile)
        if pick and pick.city:
            return pick.city
    return None
