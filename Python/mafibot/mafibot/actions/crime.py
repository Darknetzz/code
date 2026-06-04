"""Crime tab — Utfør (perform) or Stjel (steal), only when not blocked by hotel."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.crime_catalog import crime_actions_enabled
from mafibot.crime_flow import crime_flow_dry_run_summary, run_crime_flow
from mafibot.gains_ledger import source_for_crime_section
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import goto_page
from mafibot.profile_options import (
    crime_any_section_ready,
    crime_min_health_percent,
    crime_needs_steal_username,
    gameplay_paused,
)
from mafibot.state import GameState


class CrimeAction:
    name = "crime"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if gameplay_paused(profile, state):
            return False
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        min_hp = crime_min_health_percent(profile)
        if state.health_percent is not None and state.health_percent < min_hp:
            return False
        if not crime_actions_enabled(profile):
            return False
        if crime_needs_steal_username(profile):
            return False
        return crime_any_section_ready(profile, state)

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
                f"dry-run: would run crime ({crime_flow_dry_run_summary(profile)})",
            )

        await goto_page(page, "crime", policy=policy)
        await page_reading_pause(page)

        ok, detail, section = await run_crime_flow(
            page, profile, policy=policy, dry_run=dry_run
        )
        source = source_for_crime_section(section)
        if ok:
            return ActionResult(True, detail, source=source)
        return ActionResult(False, detail, source=source)
