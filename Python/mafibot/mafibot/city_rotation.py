"""Rotate travel destinations to reduce staying in one city."""

from __future__ import annotations

from datetime import datetime, timedelta

from mafibot.config import BotProfile
from mafibot.game_cities import GAME_CITIES
from mafibot.state import GameState

_last_rotation_at: datetime | None = None
_rotation_index = 0


def reset_rotation_clock() -> None:
    global _last_rotation_at, _rotation_index
    _last_rotation_at = None
    _rotation_index = 0


def _city_pool(profile: BotProfile) -> list[str]:
    pool = [c.strip() for c in profile.travel_city_pool if c.strip()]
    if pool:
        return pool
    return list(GAME_CITIES)


def rotation_destination(profile: BotProfile, state: GameState) -> str | None:
    """Next city for anti-watch rotation, or None if rotation not due."""
    global _last_rotation_at, _rotation_index
    if not profile.travel_rotate_cities:
        return None
    if not state.travel_ready:
        return None
    now = datetime.now()
    min_gap = timedelta(minutes=profile.travel_rotate_min_minutes)
    if _last_rotation_at is not None and now - _last_rotation_at < min_gap:
        return None
    pool = _city_pool(profile)
    if not pool:
        return None
    current = (state.location or "").strip()
    candidates = [c for c in pool if c.lower() != current.lower()]
    if not candidates:
        candidates = pool
    dest = candidates[_rotation_index % len(candidates)]
    _rotation_index += 1
    _last_rotation_at = now
    return dest


def note_rotation_travel() -> None:
    global _last_rotation_at
    _last_rotation_at = datetime.now()
