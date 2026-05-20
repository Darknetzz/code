"""One-off: capture Undersåtter page HTML for parser development."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_WEBBOT = _REPO.parent / "webbot"
if _WEBBOT.is_dir() and str(_WEBBOT) not in sys.path:
    sys.path.insert(0, str(_WEBBOT))

from mafibot.navigation import goto_page
from mafibot.page_capture import capture_page_html
from mafibot.session import SessionConfig, mafia_session


async def main() -> None:
    out = Path(__file__).resolve().parents[1] / "tests/fixtures/discovered/minions_folk.html"
    async with mafia_session(SessionConfig(headless=True)) as (_ctx, page):
        await page.goto("https://mafiaspillet.no/ms.php", wait_until="domcontentloaded")
        await goto_page(page, "minions", prefer_tab=True)
        await page.wait_for_timeout(2500)
        html = await capture_page_html(page)
        out.write_text(html, encoding="utf-8")
        print(f"Wrote {out} ({len(html)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
