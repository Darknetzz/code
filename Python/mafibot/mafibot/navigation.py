"""Navigate mafiaspillet.no via ?side= and human-like link clicks."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.async_api import Page

from webbot.human import human_click
from webbot.locators import resolve_locator

from mafibot.config import BASE_URL
from mafibot.human_policy import HumanPolicy, after_navigation, maybe_scroll_page
from mafibot.selectors import NAV_LINKS, side_for

_SIDE_RE = re.compile(r"[?&]side=([^&\"'#]+)", re.I)


def url_for_side(side: str) -> str:
    slug = side.lstrip("?").replace("side=", "")
    if slug.startswith("side="):
        slug = slug[5:]
    return f"{BASE_URL}?side={slug}"


async def goto_side(
    page: Page,
    logical: str,
    *,
    policy: HumanPolicy | None = None,
    prefer_link: bool = True,
) -> None:
    side = side_for(logical)
    if prefer_link and await _try_nav_link(page, logical, policy):
        return
    await page.goto(url_for_side(side), wait_until="domcontentloaded")
    await after_navigation(page, policy)


async def _try_nav_link(page: Page, logical: str, policy: HumanPolicy | None) -> bool:
    patterns = NAV_LINKS.get(logical, ())
    for pattern in patterns:
        link = page.get_by_role("link", name=re.compile(re.escape(pattern), re.I))
        if await link.count() > 0:
            loc = link.first
            if await loc.is_visible():
                await maybe_scroll_page(page, policy)
                await human_click(page, loc)
                await after_navigation(page, policy)
                return True
    return False


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
            target = loc.first
            if not await target.is_visible():
                continue
            if dry_run:
                return True
            await maybe_scroll_page(page, policy)
            await human_click(page, target)
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
