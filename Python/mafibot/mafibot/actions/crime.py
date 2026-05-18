"""Crime tab — Utfør / Stjel (only when not blocked by hotel)."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.profile_options import crime_button_labels, crime_min_health_percent
from mafibot.state import GameState


class CrimeAction:
    name = "crime"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        min_hp = crime_min_health_percent(profile)
        if state.health_percent is not None and state.health_percent < min_hp:
            return False
        return state.crime_ready

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
            return ActionResult(True, "dry-run: would run crime")

        await goto_page(page, "crime", policy=policy)
        await page_reading_pause(page)

        labels = crime_button_labels(profile)
        clicked = await click_button_matching(page, labels, policy=policy, dry_run=dry_run)
        if clicked:
            return ActionResult(True, "crime submitted")
        return ActionResult(False, "crime buttons disabled or not found (in hotel?)")
