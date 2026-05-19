"""Flyplass tab — travel / flights."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.city_rotation import note_rotation_travel, rotation_destination
from mafibot.drugs_locations import drugs_destination_needed, drugs_enabled
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.profile_options import gameplay_paused
from mafibot.navigation import click_button_matching, click_destination_matching, goto_page
from mafibot.selectors import TRAVEL_ACTION_LABELS
from mafibot.state import GameState


class TravelAction:
    name = "travel"

    def _destinations_for_run(self, profile: BotProfile, state: GameState) -> list[str]:
        drugs_dest = drugs_destination_needed(profile, state.location)
        if drugs_dest:
            return [drugs_dest]
        rotate = rotation_destination(profile, state)
        if rotate:
            return [rotate]
        return [d.strip() for d in profile.travel_destinations if d.strip()]

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if gameplay_paused(profile, state):
            return False
        if state.needs_stop or state.in_jail:
            return False
        if not state.travel_ready:
            return False
        if drugs_enabled(profile) and drugs_destination_needed(profile, state.location):
            return True
        if profile.travel_rotate_cities and rotation_destination(profile, state):
            return True
        if profile.travel_destinations:
            return True
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
        destinations = self._destinations_for_run(profile, state)
        drugs_dest = drugs_destination_needed(profile, state.location)

        if dry_run:
            dest = ", ".join(destinations) or "any"
            note = f" (for drugs → {drugs_dest})" if drugs_dest else ""
            return ActionResult(True, f"dry-run: would travel ({dest}){note}")

        await goto_page(page, "travel", policy=policy)
        await page_reading_pause(page)

        if destinations:
            picked = await click_destination_matching(
                page, destinations, policy=policy, dry_run=dry_run
            )
            if picked:
                clicked = await click_button_matching(
                    page, TRAVEL_ACTION_LABELS, policy=policy, dry_run=dry_run
                )
                if clicked:
                    if profile.travel_rotate_cities:
                        note_rotation_travel()
                    return ActionResult(True, f"travel submitted → {picked}")
            if drugs_dest:
                return ActionResult(False, f"drugs requires travel to {drugs_dest} (not on Flyplass)")
            return ActionResult(False, "preferred destination not found on Flyplass")

        clicked = await click_button_matching(page, TRAVEL_ACTION_LABELS, policy=policy, dry_run=dry_run)
        if clicked:
            return ActionResult(True, "travel action submitted")
        return ActionResult(False, "no travel button found on Flyplass")
