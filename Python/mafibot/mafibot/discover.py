"""Discovery pass for ms.php tabs and legacy ?side= links."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page
from rich.console import Console

from mafibot.auth import ensure_session
from mafibot.config import get_discovery_dir
from mafibot.selectors import GAME_TABS
from mafibot.navigation import (
    collect_side_links,
    collect_tab_labels,
    ensure_game_shell,
    goto_page,
    goto_sidebar,
)
from mafibot.selectors import DEFAULT_SIDES, merge_discovered_pages, save_pages_map
from mafibot.discover_diff import find_previous_discovery_run, write_discovery_report
from mafibot.page_capture import capture_page_html
from mafibot.state import parse_game_state

console = Console()

DISCOVERY_LOGICAL_PAGES = tuple(GAME_TABS.keys())

# Bot action pages: tabs plus sidebar-only views (ship, drugs, murder).
ACTION_SNAPSHOT_PAGES: tuple[str, ...] = (
    "crime",
    "travel",
    "hotel",
    "business",
    "ship",
    "drugs",
    "bank",
    "hospital",
    "messages",
    "family",
    "murder",
    "work",
    "minions",
    "missions",
    "organized_crime",
    "market",
)

SIDEBAR_SNAPSHOT_PAGES: frozenset[str] = frozenset(
    {"business", "ship", "drugs", "murder"}
)


async def run_discovery(
    page: Page,
    *,
    manual_login: bool = True,
    compare_last: bool = False,
) -> Path:
    out_dir = get_discovery_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = out_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Log in if needed — discovery uses ms.php.[/bold]")
    await ensure_session(page, manual=manual_login)
    await ensure_game_shell(page)

    links = await collect_side_links(page)
    tabs = await collect_tab_labels(page)
    (run_dir / "links.json").write_text(
        json.dumps(links, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "tabs.json").write_text(
        json.dumps(tabs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    console.print(f"[green]{len(links)}[/green] ?side= links, [green]{len(tabs)}[/green] tab labels")

    # Keep legacy ?side= slugs; store matched tab labels separately.
    tab_labels_by_logical: dict[str, str] = {}
    for logical, label in GAME_TABS.items():
        for t in tabs:
            if label.lower() in (t.get("label") or "").lower():
                tab_labels_by_logical[logical] = t.get("label", label)
                break

    save_pages_map(
        merge_discovered_pages(links, tabs),
        discovered_links=links,
        discovered_tabs=tabs,
        tab_labels=tab_labels_by_logical or None,
    )

    manifest: list[dict] = []
    for logical in DISCOVERY_LOGICAL_PAGES:
        try:
            await goto_page(page, logical, prefer_tab=True)
            state = await parse_game_state(page)
            safe = logical.replace("/", "_")
            html_path = run_dir / f"{safe}.html"
            png_path = run_dir / f"{safe}.png"
            html_path.write_text(await capture_page_html(page), encoding="utf-8")
            await page.screenshot(path=str(png_path), full_page=True)
            manifest.append(
                {
                    "logical": logical,
                    "tab": GAME_TABS.get(logical),
                    "url": page.url,
                    "in_hotel": state.in_hotel,
                    "hotel_blocks": state.hotel_blocks_actions,
                    "money": state.money,
                    "html": html_path.name,
                }
            )
            console.print(f"  [dim]saved[/dim] {logical}")
        except Exception as exc:
            manifest.append({"logical": logical, "error": str(exc)})
            console.print(f"  [yellow]skip[/yellow] {logical}: {exc}")

    report_path = write_discovery_report(run_dir, tabs)
    console.print(f"[green]Report:[/green] {report_path}")
    if compare_last:
        prev = find_previous_discovery_run(run_dir)
        if prev:
            from mafibot.discover_diff import compare_html_files

            changed = 0
            for html in sorted(run_dir.glob("*.html")):
                other = prev / html.name
                if other.is_file() and len(compare_html_files(html, other)) > 2:
                    changed += 1
                    console.print(f"  [yellow]changed[/yellow] {html.name} vs {prev.name}")
            if not changed:
                console.print(f"[dim]No HTML changes vs {prev.name}[/dim]")
        else:
            console.print("[dim]No previous discovery run to compare[/dim]")
    console.print("[bold]Action page snapshots…[/bold]")
    for logical in ACTION_SNAPSHOT_PAGES:
        try:
            if logical in SIDEBAR_SNAPSHOT_PAGES:
                ok = await goto_sidebar(page, logical)
                if not ok:
                    await goto_page(page, logical, prefer_tab=True)
            else:
                await goto_page(page, logical, prefer_tab=True)
            state = await parse_game_state(page)
            safe = logical.replace("/", "_")
            html_path = run_dir / f"{safe}.html"
            html_path.write_text(await capture_page_html(page), encoding="utf-8")
            await page.screenshot(path=str(run_dir / f"{safe}.png"), full_page=True)
            manifest.append(
                {
                    "logical": logical,
                    "kind": "action",
                    "url": page.url,
                    "in_hotel": state.in_hotel,
                    "html": html_path.name,
                }
            )
            console.print(f"  [dim]action[/dim] {logical}")
        except Exception as exc:
            manifest.append({"logical": logical, "kind": "action", "error": str(exc)})
            console.print(f"  [yellow]action skip[/yellow] {logical}: {exc}")

    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    from mafibot.verify_pages import run_verification

    try:
        report_path, audits = run_verification(run_dir)
        fail_count = sum(len(a.failed) for a in audits)
        console.print(
            f"[green]Verification:[/green] {report_path} "
            f"({fail_count} failed checks)"
        )
    except Exception as exc:
        console.print(f"[yellow]Verification skipped:[/yellow] {exc}")

    console.print(f"[green]Discovery output:[/green] {run_dir}")
    return run_dir
