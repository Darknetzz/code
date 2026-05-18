"""Crime tab — Utfør / Stjel (only when not blocked by hotel)."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.selectors import CRIME_ACTION_LABELS
from mafibot.state import GameState


class CrimeAction:
    name = "crime"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        if state.low_health and profile.min_health_percent > 0:
            if state.health_percent is not None and state.health_percent < profile.min_health_percent:
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

        labels = CRIME_ACTION_LABELS
        if profile.build == "angriper":
            labels = CRIME_ACTION_LABELS + ("tung",)
        elif profile.build == "okonom":
            labels = CRIME_ACTION_LABELS + ("stjel", "tyveri")

        clicked = await click_button_matching(page, labels, policy=policy, dry_run=dry_run)
        if clicked:
            return ActionResult(True, "crime submitted (Utfør/Stjel)")
        return ActionResult(False, "crime buttons disabled or not found (in hotel?)")
