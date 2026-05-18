"""Flyplass tab — travel / flights."""

from __future__ import annotations

import re

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.drugs_locations import drugs_destination_needed, drugs_enabled
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.selectors import TRAVEL_ACTION_LABELS
from mafibot.state import GameState


class TravelAction:
    name = "travel"

    def _destinations_for_run(self, profile: BotProfile, state: GameState) -> list[str]:
        drugs_dest = drugs_destination_needed(profile, state.location)
        if drugs_dest:
            return [drugs_dest]
        return [d.strip() for d in profile.travel_destinations if d.strip()]

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail:
            return False
        if not state.travel_ready:
            return False
        if drugs_enabled(profile) and drugs_destination_needed(profile, state.location):
            return True
        if profile.travel_destinations:
            return True
        return state.travel_ready

    async def _click_destination(
        self, page: Page, destinations: list[str], policy: HumanPolicy
    ) -> str | None:
        if not destinations:
            return None
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
            return city
        return None

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        destinations = self._destinations_for_run(profile, state)
        drugs_dest = drugs_destination_needed(profile, state.location)

        if dry_run:
            dest = ", ".join(destinations) or "any"
            note = f" (for drugs → {drugs_dest})" if drugs_dest else ""
            return ActionResult(True, f"dry-run: would travel ({dest}){note}")

        await goto_page(page, "travel", policy=policy)
        await page_reading_pause(page)

        if destinations:
            picked = await self._click_destination(page, destinations, policy)
            if picked:
                clicked = await click_button_matching(
                    page, TRAVEL_ACTION_LABELS, policy=policy, dry_run=dry_run
                )
                if clicked:
                    return ActionResult(True, f"travel submitted → {picked}")
            if drugs_dest:
                return ActionResult(False, f"drugs requires travel to {drugs_dest} (not on Flyplass)")
            return ActionResult(False, "preferred destination not found on Flyplass")

        clicked = await click_button_matching(page, TRAVEL_ACTION_LABELS, policy=policy, dry_run=dry_run)
        if clicked:
            return ActionResult(True, "travel action submitted")
        return ActionResult(False, "no travel button found on Flyplass")
