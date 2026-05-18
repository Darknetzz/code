"""Navigate ms.php tabs and sidebar links with human-paced clicks."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.async_api import Locator, Page

from mafibot.config import BASE_URL, GAME_URL
from mafibot.human_policy import (
    HumanPolicy,
    after_navigation,
    after_tab_change,
    human_click_paced,
    maybe_scroll_page,
    maybe_think_pause,
)
from mafibot.selectors import GAME_TABS, NAV_LINKS, SIDEBAR_LINKS, side_for, tab_label_for

_SIDE_RE = re.compile(r"[?&]side=([^&\"'#]+)", re.I)


async def ensure_game_shell(page: Page, policy: HumanPolicy | None = None) -> None:
    url = page.url.lower()
    if "ms.php" in url:
        return
    await page.goto(GAME_URL, wait_until="domcontentloaded")
    await after_navigation(page, policy)


async def goto_tab(
    page: Page,
    logical: str,
    *,
    policy: HumanPolicy | None = None,
    dry_run: bool = False,
) -> bool:
    """Open a main game tab by Norwegian label (ms.php UI)."""
    await ensure_game_shell(page, policy)
    label = tab_label_for(logical)
    if not label:
        return await goto_side(page, logical, policy=policy, dry_run=dry_run)

    tab = page.get_by_role("link", name=re.compile(rf"^{re.escape(label)}", re.I))
    if await tab.count() == 0:
        tab = page.get_by_text(re.compile(label, re.I))
    if await tab.count() == 0:
        return await _try_sidebar(page, logical, policy=policy, dry_run=dry_run)

    target = tab.first
    if not await target.is_visible():
        return False
    if dry_run:
        return True
    await maybe_think_pause(policy or HumanPolicy())
    await maybe_scroll_page(page, policy)
    await human_click_paced(page, target, policy)
    await after_tab_change(page, policy)
    return True


async def goto_sidebar(
    page: Page,
    logical: str,
    *,
    policy: HumanPolicy | None = None,
    dry_run: bool = False,
) -> bool:
    await ensure_game_shell(page, policy)
    return await _try_sidebar(page, logical, policy=policy, dry_run=dry_run)


async def _try_sidebar(
    page: Page,
    logical: str,
    *,
    policy: HumanPolicy | None = None,
    dry_run: bool = False,
) -> bool:
    patterns = SIDEBAR_LINKS.get(logical, NAV_LINKS.get(logical, ()))
    for pattern in patterns:
        link = page.get_by_role("link", name=re.compile(pattern, re.I))
        if await link.count() == 0:
            link = page.get_by_text(re.compile(pattern, re.I))
        if await link.count() == 0:
            continue
        target = link.first
        if not await target.is_visible():
            continue
        if dry_run:
            return True
        await maybe_think_pause(policy or HumanPolicy())
        await human_click_paced(page, target, policy)
        await after_navigation(page, policy)
        return True
    return False


async def goto_page(
    page: Page,
    logical: str,
    *,
    policy: HumanPolicy | None = None,
    prefer_tab: bool = True,
    dry_run: bool = False,
) -> None:
    """Prefer ms.php tab; fall back to legacy ?side= URL."""
    if prefer_tab and "ms.php" in page.url.lower():
        if await goto_tab(page, logical, policy=policy, dry_run=dry_run):
            return
        if await goto_sidebar(page, logical, policy=policy, dry_run=dry_run):
            return
    await goto_side(page, logical, policy=policy, dry_run=dry_run)


async def goto_side(
    page: Page,
    logical: str,
    *,
    policy: HumanPolicy | None = None,
    prefer_link: bool = True,
    dry_run: bool = False,
) -> None:
    if prefer_link and "ms.php" in page.url.lower():
        if await goto_tab(page, logical, policy=policy, dry_run=dry_run):
            return
    side = side_for(logical)
    await page.goto(f"{BASE_URL}?side={side}", wait_until="domcontentloaded")
    if not dry_run:
        await after_navigation(page, policy)


async def _is_actionable(locator: Locator) -> bool:
    if not await locator.is_visible():
        return False
    disabled = await locator.get_attribute("disabled")
    if disabled is not None:
        return False
    aria = await locator.get_attribute("aria-disabled")
    if aria and aria.lower() == "true":
        return False
    return True


async def click_button_matching(
    page: Page,
    labels: tuple[str, ...],
    *,
    policy: HumanPolicy | None = None,
    dry_run: bool = False,
) -> bool:
    for label in labels:
        for role in ("button", "link"):
            loc = page.get_by_role(role, name=re.compile(label, re.I))
            if await loc.count() == 0:
                continue
            for i in range(await loc.count()):
                target = loc.nth(i)
                if not await _is_actionable(target):
                    continue
                if dry_run:
                    return True
                await maybe_think_pause(policy or HumanPolicy())
                await maybe_scroll_page(page, policy)
                await human_click_paced(page, target, policy)
                await after_navigation(page, policy)
                return True
    return False


def extract_side_from_href(href: str) -> str | None:
    if not href:
        return None
    full = urljoin(BASE_URL, href)
    parsed = urlparse(full)
    qs = parse_qs(parsed.query)
    if "side" in qs and qs["side"]:
        return qs["side"][0]
    m = _SIDE_RE.search(href)
    return m.group(1) if m else None


async def collect_side_links(page: Page) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for anchor in await page.locator("a[href]").all():
        href = await anchor.get_attribute("href") or ""
        side = extract_side_from_href(href)
        if not side or side in seen:
            continue
        seen.add(side)
        try:
            text = (await anchor.inner_text()).strip()
        except Exception:
            text = ""
        out.append({"side": side, "text": text, "href": href})
    return sorted(out, key=lambda x: x["side"])


async def collect_tab_labels(page: Page) -> list[dict[str, str]]:
    tabs: list[dict[str, str]] = []
    for anchor in await page.locator("a").all():
        try:
            text = (await anchor.inner_text()).strip()
        except Exception:
            continue
        if not text or len(text) > 40:
            continue
        if text in {t["label"] for t in tabs}:
            continue
        tabs.append({"label": text})
    return tabs
