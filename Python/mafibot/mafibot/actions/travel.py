"""Flyplass tab — travel / flights."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, between_actions, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.selectors import TRAVEL_ACTION_LABELS
from mafibot.state import GameState


class TravelAction:
    name = "travel"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail or state.must_leave_hotel:
            return False
        return state.travel_ready

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
            return ActionResult(True, "dry-run: would travel")

        await goto_page(page, "travel", policy=policy)
        await page_reading_pause(page)
        clicked = await click_button_matching(page, TRAVEL_ACTION_LABELS, policy=policy, dry_run=dry_run)
        await between_actions(page, policy)
        if clicked:
            return ActionResult(True, "travel action submitted")
        return ActionResult(False, "no travel button found on Flyplass")
