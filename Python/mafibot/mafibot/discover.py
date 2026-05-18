"""Discovery pass: map ?side= links and save HTML fixtures."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page
from rich.console import Console

from mafibot.auth import ensure_session
from mafibot.config import get_discovery_dir
from mafibot.navigation import collect_side_links, goto_side, url_for_side
from mafibot.selectors import DEFAULT_SIDES, save_pages_map
from mafibot.state import parse_game_state

console = Console()

# Pages to snapshot when logged in (logical key)
DISCOVERY_LOGICAL_PAGES = (
    "home",
    "crime",
    "travel",
    "hotel",
    "work",
    "bank",
    "ship",
    "drugs",
    "messages",
    "family",
    "murder",
    "status",
)


async def run_discovery(page: Page, *, manual_login: bool = True) -> Path:
    out_dir = get_discovery_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = out_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Ensure you are logged in.[/bold]")
    await ensure_session(page, manual=manual_login)

    links = await collect_side_links(page)
    (run_dir / "links.json").write_text(
        json.dumps(links, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    console.print(f"Found [green]{len(links)}[/green] unique ?side= links")

    inferred: dict[str, str] = dict(DEFAULT_SIDES)
    for logical in DISCOVERY_LOGICAL_PAGES:
        for link in links:
            text = (link.get("text") or "").lower()
            if logical == "home" and "forside" in text:
                inferred[logical] = link["side"]
                break
            if logical in text or logical.replace("_", " ") in text:
                inferred[logical] = link["side"]
                break

    save_pages_map(inferred, discovered_links=links)
    console.print(f"Updated pages map at config (merged {len(inferred)} sides)")

    manifest: list[dict] = []
    for logical in DISCOVERY_LOGICAL_PAGES:
        try:
            await goto_side(page, logical, prefer_link=True)
            state = await parse_game_state(page)
            safe = logical.replace("/", "_")
            html_path = run_dir / f"{safe}.html"
            png_path = run_dir / f"{safe}.png"
            html_path.write_text(await page.content(), encoding="utf-8")
            await page.screenshot(path=str(png_path), full_page=True)
            manifest.append(
                {
                    "logical": logical,
                    "side": state.current_side,
                    "url": page.url,
                    "logged_in": state.logged_in,
                    "money": state.money,
                    "html": html_path.name,
                    "png": png_path.name,
                }
            )
            console.print(f"  [dim]saved[/dim] {logical} -> {state.current_side}")
        except Exception as exc:
            manifest.append({"logical": logical, "error": str(exc)})
            console.print(f"  [yellow]skip[/yellow] {logical}: {exc}")

    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    console.print(f"[green]Discovery output:[/green] {run_dir}")
    return run_dir
