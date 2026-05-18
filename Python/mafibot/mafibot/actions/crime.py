"""Crime actions."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, between_actions, page_reading_pause
from mafibot.navigation import click_button_matching, goto_side
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

        await goto_side(page, "crime", policy=policy)
        await page_reading_pause(page)

        if profile.build == "angriper":
            labels = CRIME_ACTION_LABELS + ("tung", "hard")
        elif profile.build == "okonom":
            labels = CRIME_ACTION_LABELS + ("tyveri", "lett")
        else:
            labels = CRIME_ACTION_LABELS + ("lett", "fly")

        clicked = await click_button_matching(page, labels, policy=policy)
        if not clicked:
            clicked = await click_button_matching(page, CRIME_ACTION_LABELS, policy=policy)

        await between_actions(page, policy)
        if clicked:
            return ActionResult(True, "crime action submitted")
        return ActionResult(False, "no crime button found — run discover to refine selectors")
