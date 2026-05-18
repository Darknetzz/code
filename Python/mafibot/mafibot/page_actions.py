"""Shared Playwright helpers for bank and murder pages."""

from __future__ import annotations

import re

from playwright.async_api import Locator, Page

from mafibot.human_policy import HumanPolicy, page_reading_pause

async def read_page_balances(page: Page) -> tuple[int | None, int | None]:
    """Return (wallet_cash, bank_balance) parsed from visible page text."""
    from mafibot.state import parse_game_state

    state = await parse_game_state(page)
    return state.money, state.bank_balance


def bank_adjustment(
    wallet: int | None,
    bank: int | None,
    *,
    target_cash: int,
    tolerance: int,
) -> tuple[str, int] | None:
    """
    Decide deposit or withdraw amount to move wallet toward target_cash.
    Returns (\"deposit\"|\"withdraw\", amount) or None if no change needed.
    """
    if wallet is None:
        return None
    low = target_cash - tolerance
    high = target_cash + tolerance
    if wallet < low:
        need = target_cash - wallet
        if bank is not None and bank <= 0:
            return None
        if bank is not None:
            need = min(need, bank)
        return ("withdraw", max(need, 1)) if need > 0 else None
    if wallet > high:
        excess = wallet - target_cash
        return ("deposit", max(excess, 1))
    return None


async def _find_amount_input(page: Page) -> Locator | None:
    selectors = (
        'input[name*="belop"]',
        'input[name*="beløp"]',
        'input[name*="amount"]',
        'input[name*="sum"]',
        'input[type="number"]',
        'input[type="text"]',
    )
    for sel in selectors:
        loc = page.locator(sel)
        if await loc.count() > 0:
            candidate = loc.first
            if await candidate.is_visible():
                return candidate
    return None


async def submit_bank_transfer(
    page: Page,
    direction: str,
    amount: int,
    *,
    policy: HumanPolicy,
    dry_run: bool = False,
) -> bool:
    from mafibot.navigation import click_button_matching

    if dry_run:
        return True
    labels = ("innskudd", "sett inn") if direction == "deposit" else ("uttak", "ta ut")
    field = await _find_amount_input(page)
    if field is None:
        return False
    from webbot.human import human_fill

    await human_fill(page, field, str(amount))
    await page_reading_pause(page)
    return await click_button_matching(page, labels, policy=policy)


MURDER_TARGET_INPUT_SELECTORS: tuple[str, ...] = (
    'input[name*="spiller"]',
    'input[name*="offer"]',
    'input[name*="navn"]',
    'input[name*="target"]',
    'input[name*="motstander"]',
    'input[placeholder*="spiller"]',
    'input[type="text"]',
)


async def fill_murder_target(
    page: Page,
    username: str,
    *,
    policy: HumanPolicy,
    dry_run: bool = False,
) -> bool:
    if not username.strip():
        return False
    if dry_run:
        return True
    from webbot.human import human_fill

    for sel in MURDER_TARGET_INPUT_SELECTORS:
        loc = page.locator(sel)
        count = await loc.count()
        for i in range(count):
            field = loc.nth(i)
            if not await field.is_visible():
                continue
            await human_fill(page, field, username.strip())
            await page_reading_pause(page)
            return True
    return False
