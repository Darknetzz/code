"""Oppdrag tab action."""

from __future__ import annotations

from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile
from mafibot.selectors import MISSIONS_ACTION_LABELS
from mafibot.state import GameState


class MissionsAction(_EconomyPageAction):
    logical = "missions"
    labels = MISSIONS_ACTION_LABELS
    use_sidebar = False

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.missions_enabled or not profile.missions_auto_start:
            return False
        if state.needs_stop or state.in_jail:
            return False
        if state.missions_in_progress:
            return False
        return state.missions_ready
