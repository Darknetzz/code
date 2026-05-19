"""Login and session checks for Mafiaspillet."""

from __future__ import annotations

import asyncio
import logging
import os
import re

from playwright.async_api import Page

from mafibot.config import BASE_URL, GAME_URL, load_dotenv_if_present
from mafibot.navigation import ensure_game_shell
from mafibot.state import GameState, parse_game_state

log = logging.getLogger("mafibot.auth")


async def is_logged_in(page: Page) -> bool:
    try:
        state = await parse_game_state(page)
        return state.logged_in and not state.on_login_page
    except Exception:
        return False


async def _try_env_login(page: Page) -> bool:
    load_dotenv_if_present()
    user = os.getenv("MAFIA_USER", "").strip()
    password = os.getenv("MAFIA_PASS", "").strip()
    if not user or not password:
        return False
    try:
        user_input = page.locator('input[name="brukernavn"], input[name="user"], input[type="text"]').first
        pass_input = page.locator('input[name="passord"], input[name="password"], input[type="password"]').first
        if await user_input.count() == 0 or await pass_input.count() == 0:
            return False
        await user_input.fill(user)
        await pass_input.fill(password)
        submit = page.get_by_role("button", name=re.compile(r"logg\s+inn", re.I))
        if await submit.count() == 0:
            submit = page.locator('input[type="submit"], button[type="submit"]').first
        if await submit.count() > 0:
            await submit.click()
            await page.wait_for_timeout(1500)
    except Exception as exc:
        log.debug("env login fill failed: %s", exc)
        return False
    return await is_logged_in(page)


async def ensure_session(
    page: Page,
    *,
    manual: bool = True,
    timeout_sec: float = 600.0,
) -> GameState:
    """Navigate to the game and wait until logged in."""
    url = page.url.lower()
    if "about:blank" in url or not url.startswith("http"):
        await page.goto(BASE_URL, wait_until="domcontentloaded")

    if await is_logged_in(page):
        await ensure_game_shell(page)
        return await parse_game_state(page)

    if not manual:
        if await _try_env_login(page):
            await ensure_game_shell(page)
            return await parse_game_state(page)

    deadline = asyncio.get_event_loop().time() + timeout_sec
    while asyncio.get_event_loop().time() < deadline:
        if await is_logged_in(page):
            await ensure_game_shell(page)
            return await parse_game_state(page)
        if not manual:
            await _try_env_login(page)
        await asyncio.sleep(2.0)

    state = await parse_game_state(page)
    if state.logged_in:
        await ensure_game_shell(page)
        return state
    raise TimeoutError(f"Login not detected within {timeout_sec:.0f}s — open {GAME_URL} and sign in")
