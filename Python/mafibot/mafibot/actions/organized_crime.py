"""Organisert Kriminalitet tab action."""

from __future__ import annotations

from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile
from mafibot.profile_options import crime_min_health_percent
from mafibot.selectors import ORG_CRIME_ACTION_LABELS
from mafibot.state import GameState


class OrganizedCrimeAction(_EconomyPageAction):
    logical = "organized_crime"
    labels = ORG_CRIME_ACTION_LABELS
    use_sidebar = False

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.organized_crime_enabled:
            return False
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        threshold = profile.organized_crime_min_health_percent
        if threshold is None:
            threshold = crime_min_health_percent(profile)
        if state.health_percent is not None and state.health_percent < threshold:
            return False
        return state.organized_crime_ready
