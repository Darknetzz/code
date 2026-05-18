"""Combat / murder — high risk, gated by profile."""

from __future__ import annotations

import random
import re

from playwright.async_api import Page

from mafibot.action_targets import murder_target_names, pick_murder_target
from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.page_actions import fill_murder_target
from mafibot.selectors import MURDER_ACTION_LABELS
from mafibot.state import GameState


class MurderAction:
    name = "murder"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.combat_enabled:
            return False
        if not murder_target_names(profile):
            return False
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        if profile.aggression < 0.5:
            return False
        if state.low_health_for_profile(profile.min_health_percent):
            return False
        if not state.murder_ready:
            return False
        return random.random() < profile.aggression

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        target = pick_murder_target(profile)
        if not target:
            return ActionResult(False, "murder: no target username configured")

        if dry_run:
            return ActionResult(True, f"dry-run: would target {target}")

        await goto_page(page, "murder", policy=policy)
        await page_reading_pause(page)

        if not await fill_murder_target(page, target, policy=policy, dry_run=False):
            return ActionResult(False, f"murder: could not fill target field for {target}")

        back = page.get_by_role("link", name=re.compile(r"tilbake|avbryt", re.I))
        if await back.count() > 0 and profile.aggression < 0.85:
            return ActionResult(True, f"murder: filled {target}; skipped shot (aggression gate)")

        clicked = await click_button_matching(page, MURDER_ACTION_LABELS, policy=policy)
        if clicked:
            return ActionResult(True, f"murder action submitted vs {target}")
        return ActionResult(False, f"murder: no shoot button after targeting {target}")
