"""Export a single action page fixture from a logged-in session."""

from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path

from mafibot.auth import ensure_session
from mafibot.discover import SIDEBAR_SNAPSHOT_PAGES
from mafibot.navigation import ensure_game_shell, goto_frame_route, goto_page, goto_sidebar
from mafibot.page_capture import capture_page_html
from mafibot.session import SessionConfig, mafia_session

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "discovered"


async def export(logical: str) -> None:
    async with mafia_session(SessionConfig(headless=True)) as (_, page):
        await ensure_session(page, manual=False)
        await ensure_game_shell(page)
        if logical in SIDEBAR_SNAPSHOT_PAGES:
            if not await goto_frame_route(page, logical):
                await goto_sidebar(page, logical)
        else:
            await goto_page(page, logical, prefer_tab=True)
        html = await capture_page_html(page)
        html = re.sub(r'value="[a-f0-9]{32}"', 'value="REDACTED"', html)
        out = FIXTURES / f"{logical}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"wrote {out} ({len(html)} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("logical", help="Action page id (e.g. murder)")
    args = parser.parse_args()
    asyncio.run(export(args.logical))


if __name__ == "__main__":
    main()
