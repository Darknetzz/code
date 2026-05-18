"""Combat / murder — high risk, gated by profile."""

from __future__ import annotations

import random
import re

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, between_actions, page_reading_pause
from mafibot.navigation import click_button_matching, goto_side
from mafibot.selectors import MURDER_ACTION_LABELS
from mafibot.state import GameState


class MurderAction:
    name = "murder"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.combat_enabled:
            return False
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        if profile.aggression < 0.5:
            return False
        if state.low_health:
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
        if dry_run:
            return ActionResult(True, "dry-run: would attempt murder (gated)")

        await goto_side(page, "murder", policy=policy)
        await page_reading_pause(page)
        # Prefer cancel/back if only exploring — do not chain kills
        back = page.get_by_role("link", name=re.compile(r"tilbake|avbryt", re.I))
        if await back.count() > 0 and profile.aggression < 0.85:
            return ActionResult(True, "murder page opened; skipped (aggression gate)")

        clicked = await click_button_matching(page, MURDER_ACTION_LABELS, policy=policy)
        await between_actions(page, policy)
        if clicked:
            return ActionResult(True, "murder action submitted")
        return ActionResult(False, "no murder control found")
