#!/usr/bin/env python3
"""Mafiaspillet.no human-like autopilot CLI."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

# Ensure sibling webbot package is importable when running from repo
_REPO_ROOT = Path(__file__).resolve().parent
_WEBBOT = _REPO_ROOT.parent / "webbot"
if _WEBBOT.is_dir() and str(_WEBBOT) not in sys.path:
    sys.path.insert(0, str(_WEBBOT))

from mafibot import __version__
from mafibot.auth import ensure_session, is_logged_in
from mafibot.brain import clear_stop, request_stop, run_session
from mafibot.config import BASE_URL, get_config_dir, load_bot_profile
from mafibot.discover import run_discovery
from mafibot.session import SessionConfig, mafia_session

console = Console()
app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)

TOS_WARNING = """
[bold yellow]Terms of service warning[/bold yellow]

Mafiaspillet section 7 forbids bots, scripts, and automated play.
Use may result in permanent ban and loss of progress.
This tool is for personal/educational use at your own risk.
"""


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _require_tos(accept_tos: bool) -> None:
    console.print(TOS_WARNING)
    if not accept_tos:
        console.print("[red]Pass --accept-tos to run autopilot or discovery.[/red]")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version and config paths."""
    console.print(f"mafibot {__version__}")
    console.print(f"Config: {get_config_dir()}")


@app.command()
def login(
    headless: bool = typer.Option(False, "--headless"),
    timeout: int = typer.Option(600, "--timeout", help="Seconds to wait for manual login"),
) -> None:
    """Open browser; log in manually (or via .env). Session is saved in mafibot profile."""
    _setup_logging(False)

    async def _main() -> None:
        cfg = SessionConfig(headless=headless)
        async with mafia_session(cfg) as (_ctx, page):
            console.print(f"Open {BASE_URL} and log in. Waiting up to {timeout}s…")
            state = await ensure_session(page, manual=True)
            console.print(
                f"[green]Logged in.[/green] side={state.current_side} money={state.money}"
            )
            console.print("[dim]Press Enter to close…[/dim]")
            await asyncio.get_event_loop().run_in_executor(None, input)

    asyncio.run(_main())


@app.command()
def discover(
    accept_tos: bool = typer.Option(False, "--accept-tos"),
    headless: bool = typer.Option(False, "--headless"),
) -> None:
    """Map ?side= links and save HTML/screenshots (requires login)."""
    _require_tos(accept_tos)
    _setup_logging(True)

    async def _main() -> None:
        async with mafia_session(SessionConfig(headless=headless)) as (_ctx, page):
            path = await run_discovery(page, manual_login=True)
            console.print(f"Done: {path}")

    asyncio.run(_main())


@app.command()
def run(
    profile: str = typer.Option("ranker", "--profile", "-p"),
    max_minutes: int = typer.Option(120, "--max-minutes"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log decisions without clicking"),
    accept_tos: bool = typer.Option(False, "--accept-tos"),
    headless: bool = typer.Option(False, "--headless"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run autopilot session."""
    _require_tos(accept_tos)
    _setup_logging(verbose)
    bot_profile = load_bot_profile(profile)

    async def _main() -> None:
        cfg = SessionConfig(headless=headless)
        async with mafia_session(cfg) as (_ctx, page):
            if not await is_logged_in(page):
                console.print("Not logged in — complete [bold]mafibot.py login[/bold] first.")
                await ensure_session(page, manual=True)
            console.print(f"Running profile [cyan]{bot_profile.name}[/cyan] for up to {max_minutes} min")
            if dry_run:
                console.print("[yellow]Dry-run: no clicks[/yellow]")
            try:
                await run_session(page, bot_profile, max_minutes=max_minutes, dry_run=dry_run)
            except KeyboardInterrupt:
                request_stop()
                console.print("\n[yellow]Stopped.[/yellow]")

    asyncio.run(_main())


@app.command()
def codegen() -> None:
    """Launch Playwright codegen on mafiaspillet.no (uses mafibot profile)."""
    from mafibot.config import get_profile_dir

    profile = get_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "playwright",
        "codegen",
        BASE_URL,
        f"--save-storage={profile / 'codegen_storage.json'}",
    ]
    console.print(f"Running: {' '.join(cmd)}")
    raise typer.Exit(subprocess.call(cmd))


@app.command("install-webbot-scenario")
def install_webbot_scenario() -> None:
    """Copy webbot Python scenario into %APPDATA%/webbot/scenarios/."""
    from webbot.scenario_store import get_user_scenarios_dir

    src = _REPO_ROOT / "webbot_scenario" / "mafia_autopilot.py"
    if not src.is_file():
        console.print("[red]Template missing in repo.[/red]")
        raise typer.Exit(1)
    dest_dir = get_user_scenarios_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "mafia_autopilot.py"
    content = src.read_text(encoding="utf-8").replace("{{MAFIBOT_REPO}}", str(_REPO_ROOT))
    dest.write_text(content, encoding="utf-8")
    console.print(f"[green]Installed[/green] {dest}")
    console.print("Run: [dim]cd Python/webbot && python webbot.py run mafia_autopilot --accept-tos[/dim]")


if __name__ == "__main__":
    app()
