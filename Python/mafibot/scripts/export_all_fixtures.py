"""Export all action page fixtures (requires logged-in session)."""

from __future__ import annotations

import asyncio

from mafibot.verify_pages import ACTION_PAGES

from export_fixture import export


async def main() -> None:
    for logical in ACTION_PAGES:
        print(f"--- {logical} ---")
        await export(logical)


if __name__ == "__main__":
    asyncio.run(main())
