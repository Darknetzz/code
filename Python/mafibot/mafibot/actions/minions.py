"""Undersåtter tab action."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile
from mafibot.selectors import MINIONS_ACTION_LABELS
from mafibot.state import GameState


class MinionsAction(_EconomyPageAction):
    logical = "minions"
    labels = MINIONS_ACTION_LABELS
    use_sidebar = False

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.minions_enabled:
            return False
        if state.needs_stop or state.in_jail:
            return False
        return state.minions_ready
