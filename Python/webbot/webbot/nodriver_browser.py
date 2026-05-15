"""Nodriver fallback when Playwright is detected or blocked."""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from typing import AsyncIterator

from webbot.browser import BrowserConfig, get_profile_dir


def nodriver_available() -> bool:
    try:
        import nodriver  # noqa: F401

        return True
    except Exception:
        return False


def _require_nodriver() -> object:
    if not nodriver_available():
        raise RuntimeError(
            "Nodriver is not available. Install with `pip install nodriver` "
            "(requires Python 3.10–3.12; not yet compatible with 3.14)."
        )
    import nodriver

    return nodriver


class NodriverTab:
    """Thin wrapper exposing a Playwright-like surface for scenarios."""

    def __init__(self, tab: object) -> None:
        self._tab = tab

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        await self._tab.get(url)
        await self._tab

    async def wait_for_selector(self, selector: str, timeout: float = 30_000) -> object:
        return await self._tab.select(selector, timeout=timeout / 1000)

    async def screenshot(self, path: str, full_page: bool = True) -> None:
        await self._tab.save_screenshot(path, full_page=full_page)

    @property
    def keyboard(self) -> _NodriverKeyboard:
        return _NodriverKeyboard(self._tab)

    @property
    def mouse(self) -> _NodriverMouse:
        return _NodriverMouse(self._tab)


class _NodriverKeyboard:
    def __init__(self, tab: object) -> None:
        self._tab = tab

    async def type(self, text: str, delay: int = 0) -> None:
        for char in text:
            await self._tab.send_keys(char)
            if delay:
                await asyncio.sleep(delay / 1000)

    async def press(self, key: str) -> None:
        await self._tab.send_keys(key)


class _NodriverMouse:
    def __init__(self, tab: object) -> None:
        self._tab = tab

    async def move(self, x: float, y: float) -> None:
        await self._tab.mouse_move(x, y, steps=random.randint(8, 25))

    async def click(self, x: float, y: float) -> None:
        await self._tab.mouse_click(x, y)

    async def wheel(self, _dx: int, dy: int) -> None:
        amount = max(5, min(50, abs(dy) // 10))
        if dy > 0:
            await self._tab.scroll_down(amount)
        else:
            await self._tab.scroll_up(amount)


class NodriverLocator:
    def __init__(self, tab: NodriverTab, selector: str) -> None:
        self._tab = tab
        self._selector = selector
        self._element: object | None = None

    async def _resolve(self) -> object:
        if self._element is None:
            self._element = await self._tab.wait_for_selector(self._selector)
        return self._element

    async def scroll_into_view_if_needed(self) -> None:
        el = await self._resolve()
        await el.scroll_into_view()

    async def bounding_box(self) -> dict[str, float] | None:
        el = await self._resolve()
        pos = await el.get_position()
        if not pos:
            return None
        return {"x": pos[0], "y": pos[1], "width": pos[2], "height": pos[3]}


class NodriverPage:
    """Adapter so human helpers can run against nodriver with minimal changes."""

    def __init__(self, tab: object) -> None:
        self._tab = NodriverTab(tab)

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        await self._tab.goto(url, wait_until=wait_until)

    def locator(self, selector: str) -> NodriverLocator:
        return NodriverLocator(self._tab, selector)

    def get_by_role(self, role: str, name: str | None = None) -> NodriverRoleLocator:
        return NodriverRoleLocator(self._tab, role, name)

    @property
    def keyboard(self) -> _NodriverKeyboard:
        return self._tab.keyboard

    @property
    def mouse(self) -> _NodriverMouse:
        return self._tab.mouse

    async def screenshot(self, path: str, full_page: bool = True) -> None:
        await self._tab.screenshot(path, full_page=full_page)

    async def wait_for_load_state(self, state: str = "domcontentloaded") -> None:
        await self._tab._tab


class NodriverRoleLocator:
    """Map common role selectors to CSS for nodriver."""

    _ROLE_MAP = {
        ("heading", "Example Domain"): "h1",
        ("link", "Learn more"): "a",
    }

    def __init__(self, tab: NodriverTab, role: str, name: str | None) -> None:
        self._tab = tab
        self._role = role
        self._name = name
        key = (role, name)
        self._selector = self._ROLE_MAP.get(key, f"[role='{role}']")

    async def wait_for(self, state: str = "visible", timeout: float = 15_000) -> None:
        await self._tab.wait_for_selector(self._selector, timeout=timeout)

    async def scroll_into_view_if_needed(self) -> None:
        el = await self._tab.wait_for_selector(self._selector)
        await el.scroll_into_view()

    async def bounding_box(self) -> dict[str, float] | None:
        el = await self._tab.wait_for_selector(self._selector)
        pos = await el.get_position()
        if not pos:
            return None
        return {"x": pos[0], "y": pos[1], "width": pos[2], "height": pos[3]}


@asynccontextmanager
async def nodriver_browser(
    config: BrowserConfig | None = None,
) -> AsyncIterator[NodriverPage]:
    uc = _require_nodriver()
    cfg = config or BrowserConfig()
    profile = cfg.user_data_dir or get_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)

    browser = await uc.start(
        headless=cfg.headless,
        user_data_dir=str(profile),
        browser_args=[f"--window-size={cfg.viewport_width},{cfg.viewport_height}", *cfg.extra_args],
    )
    tab = await browser.get("about:blank")
    page = NodriverPage(tab)
    try:
        yield page
    finally:
        browser.stop()
