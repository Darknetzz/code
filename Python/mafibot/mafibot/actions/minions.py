"""Undersåtter tab — train or generic action."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.profile_options import gameplay_paused
from mafibot.selectors import MINIONS_ACTION_LABELS, MINIONS_TRAIN_LABELS
from mafibot.state import GameState


class MinionsAction(_EconomyPageAction):
    logical = "minions"
    labels = MINIONS_ACTION_LABELS
    use_sidebar = False

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if gameplay_paused(profile, state):
            return False
        if not profile.minions_enabled or profile.minions_action == "disabled":
            return False
        if state.needs_stop or state.in_jail:
            return False
        if profile.minions_action == "train" and profile.minions_train_when_ready:
            if state.minions_train_ready or state.minions_ready:
                return True
            return False
        return state.minions_ready

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        if dry_run:
            return ActionResult(
                True,
                f"dry-run: minions ({profile.minions_action})",
            )

        await goto_page(page, self.logical, policy=policy, dry_run=dry_run)
        await page_reading_pause(page)

        labels = MINIONS_ACTION_LABELS
        if profile.minions_action == "train":
            labels = MINIONS_TRAIN_LABELS + labels

        clicked = await click_button_matching(page, labels, policy=policy, dry_run=dry_run)
        if clicked:
            return ActionResult(True, f"minions {profile.minions_action} submitted")
        return ActionResult(False, f"no minions control for {profile.minions_action}")
