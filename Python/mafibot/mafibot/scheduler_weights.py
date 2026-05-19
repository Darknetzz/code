"""Dynamic action ordering: Happy Hour, city income windows, missions."""

from __future__ import annotations

from datetime import datetime

from mafibot.config import BotProfile
from mafibot.missions_logic import preferred_actions_for_mission
from mafibot.state import GameState

# City payout hours (help: bymakt income at 08, 13, 17, 21)
_CITY_INCOME_HOURS: tuple[int, ...] = (8, 13, 17, 21)
_INCOME_BOOST_MINUTES_AFTER = 30

# Lower index = higher priority when scheduler reorders
_BOOST_WEIGHT: dict[str, int] = {}


def _happy_hour_boosts(state: GameState) -> dict[str, int]:
    boosts: dict[str, int] = {}
    if not state.happy_hour_active:
        return boosts
    buffs = set(state.happy_hour_buffs)
    if "double_crime_rank" in buffs or "half_crime_cooldown" in buffs:
        boosts["crime"] = boosts.get("crime", 0) + 3
    if "half_steal_cooldown" in buffs:
        boosts["crime"] = boosts.get("crime", 0) + 1
    if "half_fly_cooldown" in buffs:
        boosts["travel"] = boosts.get("travel", 0) + 2
        boosts["drugs"] = boosts.get("drugs", 0) + 1
    if "half_train_minions" in buffs:
        boosts["minions"] = boosts.get("minions", 0) + 2
    if "half_bullet_price" in buffs:
        boosts["murder"] = boosts.get("murder", 0) + 1
    return boosts


def _city_income_boost() -> dict[str, int]:
    now = datetime.now()
    if now.minute > _INCOME_BOOST_MINUTES_AFTER:
        return {}
    if now.hour not in _CITY_INCOME_HOURS:
        return {}
    return {"business": 4, "ship": 2}


def _mission_boost(state: GameState, profile: BotProfile) -> dict[str, int]:
    if not profile.missions_prioritize_when_incomplete:
        return {}
    preferred = preferred_actions_for_mission(state, profile)
    boosts: dict[str, int] = {}
    for i, action in enumerate(preferred):
        boosts[action] = boosts.get(action, 0) + (5 - min(i, 4))
    if profile.missions_enabled and state.missions_ready:
        boosts["missions"] = boosts.get("missions", 0) + 2
    return boosts


def _war_boost(state: GameState, profile: BotProfile) -> dict[str, int]:
    if not state.family_war_active:
        return {}
    boosts = {"murder": 2, "travel": 1, "crime": 1}
    if profile.combat_enabled:
        boosts["murder"] = 4
    return boosts


def action_priority_boosts(state: GameState, profile: BotProfile) -> dict[str, int]:
    """Higher value = run sooner when using weighted priority scheduler."""
    boosts: dict[str, int] = {}
    if profile.scheduler_happy_hour_boost:
        for k, v in _happy_hour_boosts(state).items():
            boosts[k] = boosts.get(k, 0) + v
    if profile.scheduler_city_income_boost:
        for k, v in _city_income_boost().items():
            boosts[k] = boosts.get(k, 0) + v
    for k, v in _mission_boost(state, profile).items():
        boosts[k] = boosts.get(k, 0) + v
    for k, v in _war_boost(state, profile).items():
        boosts[k] = boosts.get(k, 0) + v
    return boosts


def reorder_by_boosts(
    names: list[str],
    boosts: dict[str, int],
) -> list[str]:
    if not boosts:
        return names

    def sort_key(name: str) -> tuple[int, int]:
        try:
            base_idx = names.index(name)
        except ValueError:
            base_idx = len(names)
        return (-boosts.get(name, 0), base_idx)

    unique = list(dict.fromkeys(names))
    return sorted(unique, key=sort_key)
