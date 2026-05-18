"""Economy: work, hotel, ship, drugs, bank."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, between_actions, page_reading_pause
from mafibot.navigation import click_button_matching, goto_side
from mafibot.selectors import (
    DRUGS_ACTION_LABELS,
    HOTEL_ACTION_LABELS,
    SHIP_ACTION_LABELS,
    WORK_ACTION_LABELS,
)
from mafibot.state import GameState


class _EconomyPageAction:
    logical: str
    labels: tuple[str, ...]
    ready_attr: str

    @property
    def name(self) -> str:
        return self.logical

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail:
            return False
        return bool(getattr(state, self.ready_attr, True))

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
            return ActionResult(True, f"dry-run: would run {self.logical}")

        await goto_side(page, self.logical, policy=policy)
        await page_reading_pause(page)
        clicked = await click_button_matching(page, self.labels, policy=policy)
        await between_actions(page, policy)
        if clicked:
            return ActionResult(True, f"{self.logical} action submitted")
        return ActionResult(False, f"no button for {self.logical}")


class WorkAction(_EconomyPageAction):
    logical = "work"
    labels = WORK_ACTION_LABELS
    ready_attr = "work_ready"


class HotelAction(_EconomyPageAction):
    logical = "hotel"
    labels = HOTEL_ACTION_LABELS
    ready_attr = "hotel_ready"


class ShipAction(_EconomyPageAction):
    logical = "ship"
    labels = SHIP_ACTION_LABELS
    ready_attr = "ship_ready"


class DrugsAction(_EconomyPageAction):
    logical = "drugs"
    labels = DRUGS_ACTION_LABELS
    ready_attr = "drugs_ready"


class BankAction(_EconomyPageAction):
    logical = "bank"
    labels = ("innskudd", "uttak", "overfør", "bank")
    ready_attr = "work_ready"  # bank has no dedicated timer in parser; piggyback

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail:
            return False
        return "bank" in profile.economy_order
