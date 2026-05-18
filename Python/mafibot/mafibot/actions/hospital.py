"""Sykehus tab — heal when health drops below profile threshold."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.profile_options import hospital_enabled, needs_hospital_visit
from mafibot.selectors import HOSPITAL_ACTION_LABELS
from mafibot.state import GameState


class HospitalAction:
    name = "hospital"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not hospital_enabled(profile):
            return False
        if state.needs_stop or state.in_jail:
            return False
        if not needs_hospital_visit(profile, state):
            return False
        return state.hospital_ready

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        threshold = profile.hospital_health_threshold
        hp = state.health_percent
        if dry_run:
            return ActionResult(
                True,
                f"dry-run: would visit Sykehus (health {hp}% < {threshold}%)",
            )

        await goto_page(page, "hospital", policy=policy)
        await page_reading_pause(page)

        clicked = await click_button_matching(
            page, HOSPITAL_ACTION_LABELS, policy=policy, dry_run=dry_run
        )
        if clicked:
            return ActionResult(True, f"hospital treatment submitted ({hp}% → heal)")
        return ActionResult(False, "hospital: no treatment button found on Sykehus")
