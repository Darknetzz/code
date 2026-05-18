"""Flyplass tab — travel / flights."""

from __future__ import annotations

import re

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.selectors import TRAVEL_ACTION_LABELS
from mafibot.state import GameState


class TravelAction:
    name = "travel"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail:
            return False
        return state.travel_ready

    async def _click_destination(self, page: Page, profile: BotProfile, policy: HumanPolicy) -> bool:
        destinations = [d.strip() for d in profile.travel_destinations if d.strip()]
        if not destinations:
            return False
        from webbot.human import human_click

        for city in destinations:
            link = page.get_by_role("link", name=re.compile(re.escape(city), re.I))
            if await link.count() == 0:
                link = page.get_by_text(re.compile(re.escape(city), re.I))
            if await link.count() == 0:
                continue
            target = link.first
            if not await target.is_visible():
                continue
            await human_click(page, target)
            await page_reading_pause(page)
            return True
        return False

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
            dest = ", ".join(profile.travel_destinations) or "any"
            return ActionResult(True, f"dry-run: would travel ({dest})")

        await goto_page(page, "travel", policy=policy)
        await page_reading_pause(page)

        if profile.travel_destinations:
            if await self._click_destination(page, profile, policy):
                clicked = await click_button_matching(
                    page, TRAVEL_ACTION_LABELS, policy=policy, dry_run=dry_run
                )
                if clicked:
                    return ActionResult(True, "travel submitted for preferred destination")
            return ActionResult(False, "preferred destination not found on Flyplass")

        clicked = await click_button_matching(page, TRAVEL_ACTION_LABELS, policy=policy, dry_run=dry_run)
        if clicked:
            return ActionResult(True, "travel action submitted")
        return ActionResult(False, "no travel button found on Flyplass")
