"""Marked tab action — rate limited."""

from __future__ import annotations

from datetime import datetime, timedelta

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.selectors import MARKET_ACTION_LABELS
from mafibot.state import GameState

_market_this_hour = 0
_hour_started: datetime | None = None


def _can_market_trade(profile: BotProfile) -> bool:
    global _market_this_hour, _hour_started
    if profile.market_max_per_hour <= 0:
        return False
    now = datetime.now()
    if _hour_started is None or now - _hour_started > timedelta(hours=1):
        _hour_started = now
        _market_this_hour = 0
    return _market_this_hour < profile.market_max_per_hour


class MarketAction(_EconomyPageAction):
    logical = "market"
    labels = MARKET_ACTION_LABELS
    use_sidebar = False

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.market_enabled or profile.market_mode == "none":
            return False
        if state.needs_stop or state.in_jail:
            return False
        if not _can_market_trade(profile):
            return False
        return state.market_ready

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        global _market_this_hour
        if dry_run:
            return ActionResult(True, f"dry-run: would run market ({profile.market_mode})")

        await goto_page(page, self.logical, policy=policy, dry_run=dry_run)
        await page_reading_pause(page)

        labels = list(MARKET_ACTION_LABELS)
        if profile.market_mode == "sell_junk":
            labels = ("selg", "legg ut") + labels
        elif profile.market_mode == "buy_supplies":
            labels = ("kjøp", "handel") + labels

        clicked = await click_button_matching(page, labels, policy=policy, dry_run=dry_run)
        if clicked:
            _market_this_hour += 1
            return ActionResult(True, f"market {profile.market_mode} submitted")
        return ActionResult(False, "no market control found")
