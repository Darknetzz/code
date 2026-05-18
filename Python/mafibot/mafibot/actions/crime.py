"""Crime tab — Utfør (perform) or Stjel (steal), only when not blocked by hotel."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.crime_flow import run_crime_flow
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import goto_page
from mafibot.profile_options import crime_min_health_percent, crime_steal_target_mode, crime_steal_username
from mafibot.state import GameState


class CrimeAction:
    name = "crime"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        min_hp = crime_min_health_percent(profile)
        if state.health_percent is not None and state.health_percent < min_hp:
            return False
        if profile.crime_kind == "steal" and crime_steal_target_mode(profile) == "specific":
            if not crime_steal_username(profile):
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
            kind = profile.crime_kind
            extra = ""
            if kind == "steal":
                extra = f" steal={profile.crime_steal_what} target={profile.crime_steal_target_mode}"
            elif profile.crime_perform_type != "any":
                extra = f" perform={profile.crime_perform_type}"
            return ActionResult(True, f"dry-run: would run crime ({kind}{extra})")

        await goto_page(page, "crime", policy=policy)
        await page_reading_pause(page)

        ok, detail = await run_crime_flow(page, profile, policy=policy, dry_run=dry_run)
        if ok:
            return ActionResult(True, detail)
        return ActionResult(False, detail)
