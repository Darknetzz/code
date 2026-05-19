"""Mission requirement hints → preferred bot actions."""

from __future__ import annotations

from mafibot.config import BotProfile, MissionsMode
from mafibot.state import GameState

# Maps mission_requirement_hint / mission text themes to economy_order action ids
_HINT_TO_ACTIONS: dict[str, list[str]] = {
    "crime": ["crime"],
    "minions_train": ["minions"],
    "buy_weapon": ["market", "crime"],
    "buy_car": ["market"],
    "business": ["business"],
    "ship": ["ship"],
    "travel": ["travel"],
    "club": ["travel"],
    "murder": ["murder", "crime"],
}


def missions_mode_effective(profile: BotProfile) -> MissionsMode:
    if not profile.missions_enabled:
        return "off"
    return profile.missions_mode


def mission_needs_progress(state: GameState) -> bool:
    if state.mission_progress_remaining() is not None:
        return state.mission_progress_remaining() > 0
    if state.missions_in_progress:
        return True
    if state.mission_requirement_hint:
        return True
    return False


def preferred_actions_for_mission(state: GameState, profile: BotProfile) -> list[str]:
    """Actions that advance the current mission (auto_progress mode)."""
    if missions_mode_effective(profile) != "auto_progress":
        return []
    if not mission_needs_progress(state) and not state.missions_ready:
        return []

    hint = state.mission_requirement_hint
    if hint and hint in _HINT_TO_ACTIONS:
        return list(_HINT_TO_ACTIONS[hint])

    # Early missions without parsed hint
    if state.mission_number is not None and state.mission_number <= 9:
        if state.mission_number <= 2:
            return ["crime", "market"]
        if state.mission_number <= 7:
            return ["crime", "minions", "business", "ship"]
        return ["crime", "minions", "murder"]

    return ["crime", "missions"]
