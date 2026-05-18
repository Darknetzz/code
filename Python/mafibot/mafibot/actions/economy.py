"""Economy: sidebar bedrifter/rederi + legacy pages."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page, goto_sidebar
from mafibot.selectors import DRUGS_ACTION_LABELS, SHIP_ACTION_LABELS, WORK_ACTION_LABELS
from mafibot.state import GameState


class _EconomyPageAction:
    logical: str
    labels: tuple[str, ...]
    use_sidebar: bool = False

    @property
    def name(self) -> str:
        return self.logical

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail:
            return False
        if self.logical == "business":
            return state.business_income_ready
        if self.logical == "ship":
            return state.ship_in_port or state.ship_ready
        return True

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

        if self.use_sidebar:
            ok = await goto_sidebar(page, self.logical, policy=policy, dry_run=dry_run)
        else:
            ok = await goto_page(page, self.logical, policy=policy, dry_run=dry_run)
        if not ok and not dry_run:
            await goto_page(page, self.logical, policy=policy)

        await page_reading_pause(page)
        clicked = await click_button_matching(page, self.labels, policy=policy, dry_run=dry_run)
        if clicked or dry_run:
            return ActionResult(True, f"{self.logical} action submitted")
        return ActionResult(False, f"no button for {self.logical}")


class BusinessAction(_EconomyPageAction):
    logical = "business"
    labels = WORK_ACTION_LABELS + ("hent", "inntekt")
    use_sidebar = True


class ShipAction(_EconomyPageAction):
    logical = "ship"
    labels = SHIP_ACTION_LABELS
    use_sidebar = True


class DrugsAction(_EconomyPageAction):
    logical = "drugs"
    labels = DRUGS_ACTION_LABELS
    use_sidebar = True


class BankAction(_EconomyPageAction):
    logical = "bank"
    labels = ("innskudd", "uttak", "overfør", "bank")

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail:
            return False
        return "bank" in profile.economy_order
