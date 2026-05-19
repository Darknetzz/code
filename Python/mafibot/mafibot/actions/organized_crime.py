"""Organisert Kriminalitet tab — difficulty selection."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile, OrganizedCrimeDifficulty
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, click_option_matching, goto_page
from mafibot.profile_options import crime_min_health_percent, gameplay_paused
from mafibot.selectors import ORG_CRIME_ACTION_LABELS, org_crime_difficulty_labels
from mafibot.state import GameState

_DIFFICULTY_ORDER: tuple[OrganizedCrimeDifficulty, ...] = (
    "lett",
    "medium",
    "hard",
)


class OrganizedCrimeAction(_EconomyPageAction):
    logical = "organized_crime"
    labels = ORG_CRIME_ACTION_LABELS
    use_sidebar = False

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if gameplay_paused(profile, state):
            return False
        if not profile.organized_crime_enabled:
            return False
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        threshold = profile.organized_crime_min_health_percent
        if threshold is None:
            threshold = crime_min_health_percent(profile)
        if state.health_percent is not None and state.health_percent < threshold:
            return False
        return state.organized_crime_ready

    def _difficulty_labels(self, profile: BotProfile) -> list[str]:
        diff = profile.organized_crime_difficulty
        if diff == "auto":
            return list(org_crime_difficulty_labels("medium"))
        return list(org_crime_difficulty_labels(diff))

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
                f"dry-run: org crime ({profile.organized_crime_difficulty})",
            )

        await goto_page(page, self.logical, policy=policy, dry_run=dry_run)
        await page_reading_pause(page)

        if profile.organized_crime_difficulty == "auto":
            for level in _DIFFICULTY_ORDER:
                labels = org_crime_difficulty_labels(level)
                if await click_option_matching(page, labels, policy=policy, dry_run=dry_run):
                    break
        else:
            labels = self._difficulty_labels(profile)
            await click_option_matching(page, labels, policy=policy, dry_run=dry_run)

        clicked = await click_button_matching(
            page, ORG_CRIME_ACTION_LABELS, policy=policy, dry_run=dry_run
        )
        if clicked:
            return ActionResult(
                True,
                f"organized crime ({profile.organized_crime_difficulty}) submitted",
            )
        return ActionResult(False, "no organized crime button found")
