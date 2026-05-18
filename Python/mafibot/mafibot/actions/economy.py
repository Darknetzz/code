"""Economy: sidebar bedrifter/rederi + legacy pages."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page, goto_sidebar
from mafibot.page_actions import bank_adjustment, read_page_balances, submit_bank_transfer
from mafibot.profile_options import drugs_click_labels
from mafibot.selectors import SHIP_ACTION_LABELS, WORK_ACTION_LABELS
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
            if profile.business_only_when_income_ready:
                return state.business_income_ready
            return True
        if self.logical == "ship":
            if profile.ship_only_when_in_port:
                return state.ship_in_port or state.ship_ready
            return True
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
    labels = ("kjøp", "selg", "narkotika")
    use_sidebar = True

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
            return ActionResult(True, f"dry-run: would run drugs ({profile.drugs_prefer})")

        if self.use_sidebar:
            ok = await goto_sidebar(page, self.logical, policy=policy, dry_run=dry_run)
        else:
            ok = await goto_page(page, self.logical, policy=policy, dry_run=dry_run)
        if not ok and not dry_run:
            await goto_page(page, self.logical, policy=policy)

        await page_reading_pause(page)
        labels = drugs_click_labels(profile)
        clicked = await click_button_matching(page, labels, policy=policy, dry_run=dry_run)
        if clicked or dry_run:
            return ActionResult(True, f"drugs action submitted ({profile.drugs_prefer})")
        return ActionResult(False, f"no button for drugs ({profile.drugs_prefer})")


class BankAction:
    name = "bank"
    labels = ("innskudd", "uttak", "overfør", "bank")

    def _planned_adjustment(
        self, state: GameState, profile: BotProfile
    ) -> tuple[str, int] | None:
        if not profile.bank_auto_balance:
            return None
        return bank_adjustment(
            state.money,
            state.bank_balance,
            target_cash=profile.bank_keep_cash_on_hand,
            tolerance=profile.bank_balance_tolerance,
        )

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail:
            return False
        if "bank" not in profile.economy_order:
            return False
        if profile.bank_auto_balance:
            if state.money is None:
                return False
            return self._planned_adjustment(state, profile) is not None
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
            plan = self._planned_adjustment(state, profile)
            if profile.bank_auto_balance and plan:
                direction, amount = plan
                return ActionResult(
                    True,
                    f"dry-run: would {direction} {amount} kr (target wallet {profile.bank_keep_cash_on_hand})",
                )
            return ActionResult(True, "dry-run: would open bank")

        await goto_page(page, "bank", policy=policy)
        await page_reading_pause(page)

        if profile.bank_auto_balance:
            wallet, bank = await read_page_balances(page)
            plan = bank_adjustment(
                wallet,
                bank,
                target_cash=profile.bank_keep_cash_on_hand,
                tolerance=profile.bank_balance_tolerance,
            )
            if plan is None:
                return ActionResult(True, "bank: wallet already within target range")
            direction, amount = plan
            ok = await submit_bank_transfer(
                page, direction, amount, policy=policy, dry_run=False
            )
            if ok:
                return ActionResult(
                    True,
                    f"bank {direction} {amount} kr (wallet target {profile.bank_keep_cash_on_hand})",
                )
            return ActionResult(False, f"bank {direction} failed (no form/button)")

        clicked = await click_button_matching(page, self.labels, policy=policy)
        if clicked:
            return ActionResult(True, "bank action submitted (manual mode)")
        return ActionResult(False, "no bank control found")
