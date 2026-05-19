"""Playwright persistent browser context management."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from playwright.async_api import BrowserContext, Page, async_playwright


@dataclass
class BrowserConfig:
    headless: bool = False
    channel: str | None = "chrome"
    slow_mo: int = 0
    ignore_https_errors: bool = False
    viewport_width: int = 1280
    viewport_height: int = 720
    user_data_dir: Path | None = None
    proxy: dict[str, str] | None = None
    extra_args: list[str] = field(
        default_factory=lambda: ["--disable-blink-features=AutomationControlled"]
    )


def get_app_config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "webbot"


def get_profile_dir() -> Path:
    return get_app_config_dir() / "profile"


def get_screenshots_dir() -> Path:
    return get_app_config_dir() / "screenshots"


def _launch_kwargs(config: BrowserConfig, profile: Path) -> dict:
    kwargs: dict = {
        "user_data_dir": str(profile),
        "headless": config.headless,
        "viewport": {
            "width": config.viewport_width,
            "height": config.viewport_height,
        },
        "args": list(config.extra_args),
        "ignore_default_args": ["--enable-automation"],
    }
    if config.channel:
        kwargs["channel"] = config.channel
    if config.slow_mo:
        kwargs["slow_mo"] = config.slow_mo
    if config.ignore_https_errors:
        kwargs["ignore_https_errors"] = True
    if config.proxy:
        kwargs["proxy"] = config.proxy
    return kwargs


@asynccontextmanager
async def persistent_browser(
    config: BrowserConfig | None = None,
) -> AsyncIterator[tuple[BrowserContext, Page]]:
    """Launch a headed/headless Chromium with a persistent user profile."""
    cfg = config or BrowserConfig()
    profile = cfg.user_data_dir or get_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        kwargs = _launch_kwargs(cfg, profile)
        try:
            context = await playwright.chromium.launch_persistent_context(**kwargs)
        except Exception:
            kwargs.pop("channel", None)
            context = await playwright.chromium.launch_persistent_context(**kwargs)

        page = context.pages[0] if context.pages else await context.new_page()
        try:
            yield context, page
        finally:
            await context.close()


async def save_failure_screenshot(page: Page, name: str) -> Path | None:
    """Capture a screenshot when a scenario fails."""
    try:
        screenshots_dir = get_screenshots_dir()
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        path = screenshots_dir / f"{name}.png"
        await page.screenshot(path=str(path), full_page=True)
        return path
    except Exception:
        return None
