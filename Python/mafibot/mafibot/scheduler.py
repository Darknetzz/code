"""Action selection helpers (priority vs soonest-ready cooldown)."""

from __future__ import annotations

from datetime import datetime

from mafibot.actions.base import Action
from mafibot.config import BotProfile
from mafibot.hotel_stay import action_requires_leave_hotel
from mafibot.profile_options import hospital_enabled, needs_hospital_visit
from mafibot.state import GameState

_ROTATION_EXCLUDE = frozenset({"leave_hotel", "book_hotel", "hotel"})


def ordered_action_names(profile: BotProfile, state: GameState | None = None) -> list[str]:
    order: list[str] = []
    for name in profile.economy_order:
        if name in _ROTATION_EXCLUDE:
            continue
        if name not in order:
            order.append(name)
    if profile.social_enabled:
        for s in ("messages", "family"):
            if s not in order:
                order.append(s)
    if profile.combat_enabled and "murder" not in order:
        order.append("murder")
    normalized: list[str] = []
    for n in order:
        if n == "work":
            n = "business"
        if n not in normalized:
            normalized.append(n)
    if state is not None:
        if (
            hospital_enabled(profile)
            and needs_hospital_visit(profile, state)
            and "hospital" in normalized
        ):
            normalized = ["hospital"] + [n for n in normalized if n != "hospital"]
    return normalized


def _cooldown_ready_at(state: GameState, action_id: str) -> datetime | None:
    for cd in state.active_cooldowns:
        if cd.id == action_id and cd.ready_at is not None:
            return cd.ready_at
    ready_map = {
        "crime": state.crime_ready,
        "travel": state.travel_ready,
        "business": state.work_ready,
        "ship": state.ship_ready,
        "drugs": state.drugs_ready,
        "murder": state.murder_ready,
        "hospital": state.hospital_ready,
    }
    if ready_map.get(action_id, True):
        return datetime.now()
    return None


async def action_block_reason(
    action: Action,
    state: GameState,
    profile: BotProfile,
) -> str | None:
    """Human-readable reason when can_run is false."""
    if state.needs_stop:
        return "session stop (captcha, ban, or logged out)"
    if state.in_jail:
        return "in jail"
    if action.name == "crime" and state.in_hospital:
        return "in hospital"
    if not await action.can_run(state, profile):
        if action.name == "crime" and not state.crime_ready:
            return "crime on cooldown"
        if action.name == "travel" and not state.travel_ready:
            return "travel on cooldown"
        if action.name == "business" and not state.work_ready:
            return "business not ready"
        if action.name == "ship" and not state.ship_ready:
            return "ship not ready"
        if profile.stay_in_hotel and action_requires_leave_hotel(action.name) and state.in_hotel:
            if state.hotel_blocks_actions:
                pass
        hp = getattr(state, "health_percent", None)
        if action.name == "crime" and hp is not None:
            from mafibot.profile_options import crime_min_health_percent

            if hp < crime_min_health_percent(profile):
                return f"health below {crime_min_health_percent(profile)}%"
        return "not ready"
    return None


async def pick_runnable_actions(
    state: GameState,
    profile: BotProfile,
    actions: list[Action],
) -> list[tuple[Action, str]]:
    """Actions that can_run, with selection hint."""
    runnable: list[tuple[Action, str]] = []
    for action in actions:
        if not await action.can_run(state, profile):
            continue
        hint = ""
        if profile.stay_in_hotel and action_requires_leave_hotel(action.name) and state.in_hotel:
            hint = " (will leave hotel first)"
        runnable.append((action, hint))
    return runnable


def pick_soonest_ready(
    runnable: list[tuple[Action, str]],
    state: GameState,
) -> tuple[Action, str] | None:
    if not runnable:
        return None
    if len(runnable) == 1:
        action, hint = runnable[0]
        return action, f"soonest: {action.name}{hint}"

    def sort_key(item: tuple[Action, str]) -> datetime:
        action, _ = item
        ready = _cooldown_ready_at(state, action.name)
        return ready or datetime.max

    runnable_sorted = sorted(runnable, key=sort_key)
    action, hint = runnable_sorted[0]
    return action, f"soonest: {action.name}{hint}"
