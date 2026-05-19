"""Persistent browser session for Mafiaspillet."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from playwright.async_api import BrowserContext, Page

from webbot.browser import BrowserConfig, persistent_browser, save_failure_screenshot

from mafibot.config import get_profile_dir


@dataclass
class SessionConfig:
    headless: bool = False
    channel: str | None = "chrome"
    slow_mo: int = 0
    ignore_https_errors: bool = False
    viewport_width: int = 1280
    viewport_height: int = 900
    proxy_server: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None


def _proxy_from_env() -> dict[str, str] | None:
    server = os.getenv("MAFIBOT_PROXY_SERVER", "").strip()
    if not server:
        return None
    proxy: dict[str, str] = {"server": server}
    user = os.getenv("MAFIBOT_PROXY_USERNAME", "").strip()
    password = os.getenv("MAFIBOT_PROXY_PASSWORD", "").strip()
    if user:
        proxy["username"] = user
    if password:
        proxy["password"] = password
    return proxy


def browser_config(cfg: SessionConfig | None = None) -> BrowserConfig:
    c = cfg or SessionConfig()
    proxy: dict[str, str] | None = None
    if c.proxy_server:
        proxy = {"server": c.proxy_server}
        if c.proxy_username:
            proxy["username"] = c.proxy_username
        if c.proxy_password:
            proxy["password"] = c.proxy_password
    else:
        proxy = _proxy_from_env()
    return BrowserConfig(
        headless=c.headless,
        channel=c.channel,
        slow_mo=c.slow_mo,
        ignore_https_errors=c.ignore_https_errors,
        viewport_width=c.viewport_width,
        viewport_height=c.viewport_height,
        user_data_dir=get_profile_dir(),
        proxy=proxy,
    )


@asynccontextmanager
async def mafia_session(
    cfg: SessionConfig | None = None,
) -> AsyncIterator[tuple[BrowserContext, Page]]:
    async with persistent_browser(browser_config(cfg)) as pair:
        yield pair


async def capture_failure(page: Page, label: str) -> str | None:
    path = await save_failure_screenshot(page, f"mafibot_{label}")
    return str(path) if path else None
