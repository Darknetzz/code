"""Oppdrag tab — start missions and auto-progress via delegated actions."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile
from mafibot.missions_logic import missions_mode_effective
from mafibot.profile_options import gameplay_paused
from mafibot.selectors import MISSIONS_ACTION_LABELS
from mafibot.state import GameState


class MissionsAction(_EconomyPageAction):
    logical = "missions"
    labels = MISSIONS_ACTION_LABELS
    use_sidebar = False

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if gameplay_paused(profile, state):
            return False
        if not profile.missions_enabled:
            return False
        mode = missions_mode_effective(profile)
        if mode == "off":
            return False
        if state.needs_stop or state.in_jail:
            return False
        if mode == "start_only":
            return (
                state.missions_ready
                and not state.missions_in_progress
                and profile.missions_auto_start
            )
        if state.missions_ready and not state.missions_in_progress:
            return profile.missions_auto_start
        if state.missions_in_progress:
            remaining = state.mission_progress_remaining()
            return remaining is not None and remaining == 0
        return False

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        if dry_run:
            mode = missions_mode_effective(profile)
            return ActionResult(True, f"dry-run: missions tab ({mode})")
        return await super().run(page, state, profile, policy, dry_run=dry_run)
