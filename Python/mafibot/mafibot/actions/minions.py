"""Undersåtter tab — per-minion training and train-all."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.minions_page import (
    apply_minions_training,
    click_train_all,
    ensure_folk_train_page,
    parse_minions_page,
)
from mafibot.navigation import click_button_matching
from mafibot.profile_options import gameplay_paused
from mafibot.selectors import MINIONS_ACTION_LABELS
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

        await ensure_folk_train_page(page, policy=policy, dry_run=dry_run)
        roster = await parse_minions_page(page)

        if profile.minions_action == "train":
            updated = await apply_minions_training(page, profile, roster, dry_run=dry_run)
            await page_reading_pause(page)
            if await click_train_all(page, policy=policy, dry_run=dry_run):
                detail = f"minions train ({roster.alive_count} alive"
                if updated:
                    detail += f", set training for {', '.join(updated)}"
                detail += ")"
                return ActionResult(True, detail)
            return ActionResult(False, "minions: Tren alle button not found")

        labels = MINIONS_ACTION_LABELS
        clicked = await click_button_matching(page, labels, policy=policy, dry_run=dry_run)
        if clicked:
            return ActionResult(True, f"minions {profile.minions_action} submitted")
        return ActionResult(False, f"no minions control for {profile.minions_action}")
