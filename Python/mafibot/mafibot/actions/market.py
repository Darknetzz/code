"""Marked tab — buy supplies / sell junk, mission-aware."""

from __future__ import annotations

from datetime import datetime, timedelta

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.actions.economy import _EconomyPageAction
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.missions_logic import missions_mode_effective
from mafibot.navigation import click_button_matching, click_option_matching, goto_page
from mafibot.profile_options import gameplay_paused
from mafibot.selectors import MARKET_ACTION_LABELS, market_item_labels
from mafibot.state import GameState

_market_this_hour = 0
_hour_started: datetime | None = None

_MISSION_BUY_HINTS = frozenset({"buy_weapon", "buy_car"})


def _can_market_trade(profile: BotProfile) -> bool:
    global _market_this_hour, _hour_started
    if profile.market_max_per_hour <= 0:
        return False
    now = datetime.now()
    if _hour_started is None or now - _hour_started > timedelta(hours=1):
        _hour_started = now
        _market_this_hour = 0
    return _market_this_hour < profile.market_max_per_hour


def _mission_wants_buy(state: GameState, profile: BotProfile) -> bool:
    if not profile.market_buy_when_mission_needs:
        return False
    if missions_mode_effective(profile) == "off":
        return False
    hint = state.mission_requirement_hint
    return hint in _MISSION_BUY_HINTS


class MarketAction(_EconomyPageAction):
    logical = "market"
    labels = MARKET_ACTION_LABELS
    use_sidebar = False

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if gameplay_paused(profile, state):
            return False
        if not profile.market_enabled or profile.market_mode == "none":
            if not _mission_wants_buy(state, profile):
                return False
        if state.needs_stop or state.in_jail:
            return False
        if not _can_market_trade(profile):
            return False
        return state.market_ready

    def _buy_item_ids(self, profile: BotProfile, state: GameState) -> list[str]:
        items = list(profile.market_buy_items)
        if _mission_wants_buy(state, profile):
            hint = state.mission_requirement_hint
            if hint == "buy_weapon" and "våpen" not in items:
                items.append("våpen")
            if hint == "buy_car" and "bil" not in items:
                items.append("bil")
        return items

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
        mode = profile.market_mode
        if _mission_wants_buy(state, profile) and mode == "none":
            mode = "buy_supplies"

        if dry_run:
            return ActionResult(True, f"dry-run: market ({mode})")

        await goto_page(page, self.logical, policy=policy, dry_run=dry_run)
        await page_reading_pause(page)

        if mode == "buy_supplies":
            for item_id in self._buy_item_ids(profile, state):
                labels = market_item_labels(item_id)
                if await click_option_matching(page, labels, policy=policy, dry_run=dry_run):
                    clicked = await click_button_matching(
                        page, ("kjøp", "handel", "bekreft") + MARKET_ACTION_LABELS,
                        policy=policy,
                        dry_run=dry_run,
                    )
                    if clicked:
                        _market_this_hour += 1
                        return ActionResult(True, f"market bought {item_id}")
        elif mode == "sell_junk":
            for item_id in profile.market_sell_items:
                labels = market_item_labels(item_id)
                await click_option_matching(page, labels, policy=policy, dry_run=dry_run)
            clicked = await click_button_matching(
                page, ("selg", "legg ut") + MARKET_ACTION_LABELS,
                policy=policy,
                dry_run=dry_run,
            )
            if clicked:
                _market_this_hour += 1
                return ActionResult(True, "market sell submitted")

        labels = list(MARKET_ACTION_LABELS)
        if mode == "sell_junk":
            labels = ("selg", "legg ut") + labels
        elif mode == "buy_supplies":
            labels = ("kjøp", "handel") + labels

        clicked = await click_button_matching(page, labels, policy=policy, dry_run=dry_run)
        if clicked:
            _market_this_hour += 1
            return ActionResult(True, f"market {mode} submitted")
        return ActionResult(False, "no market control found")
