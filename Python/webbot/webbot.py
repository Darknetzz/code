#!/usr/bin/env python3
"""
Webbot - Human-like browser automation
Uses Playwright (with nodriver fallback) to click and type on web pages naturally.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import webbrowser
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from webbot import __version__
from webbot.browser import get_profile_dir
from webbot.nodriver_browser import nodriver_available, nodriver_browser
from webbot.runner import RunConfig, get_runner
from webbot.scenarios import get_scenario, list_scenario_info

console = Console()
app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)


class Driver(str, Enum):
    playwright = "playwright"
    nodriver = "nodriver"


async def _open_url_playwright(url: str, headless: bool, channel: Optional[str], slow_mo: int) -> None:
    from webbot.browser import BrowserConfig, persistent_browser

    config = BrowserConfig(headless=headless, channel=channel or "chrome", slow_mo=slow_mo)
    async with persistent_browser(config) as (_context, page):
        await page.goto(url, wait_until="domcontentloaded")
        console.print(f"[green]Opened[/green] {url}")
        console.print("[dim]Close the browser window to exit.[/dim]")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            return


async def _open_url_nodriver(url: str, headless: bool) -> None:
    from webbot.browser import BrowserConfig

    config = BrowserConfig(headless=headless)
    async with nodriver_browser(config) as page:
        await page.goto(url)
        console.print(f"[green]Opened[/green] {url} [dim](nodriver)[/dim]")
        console.print("[dim]Press Ctrl+C to exit.[/dim]")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            return


@app.command()
def open(
    url: str = typer.Argument(..., help="URL to open in a persistent browser session"),
    headless: bool = typer.Option(False, "--headless", help="Run without a visible window"),
    driver: Driver = typer.Option(Driver.playwright, "--driver", help="Browser backend"),
    channel: Optional[str] = typer.Option(
        "chrome",
        "--channel",
        help="Playwright browser channel (chrome, msedge, chromium). Ignored by nodriver.",
    ),
    slow_mo: int = typer.Option(0, "--slow-mo", help="Playwright slow-motion delay in ms"),
):
    """Open a URL in a headed browser with a saved profile (cookies persist)."""
    if driver == Driver.nodriver:
        if not nodriver_available():
            console.print(
                "[bold red]Nodriver is not available on this Python version. "
                "Use --driver playwright (default) or Python 3.10–3.12 with nodriver installed.[/bold red]"
            )
            raise typer.Exit(1)
        asyncio.run(_open_url_nodriver(url, headless))
    else:
        asyncio.run(_open_url_playwright(url, headless, channel, slow_mo))


@app.command("run")
def run_scenario(
    scenario: str = typer.Argument(..., help="Scenario name to execute"),
    headless: bool = typer.Option(False, "--headless", help="Run without a visible window"),
    driver: Driver = typer.Option(Driver.playwright, "--driver", help="Browser backend"),
    channel: Optional[str] = typer.Option("chrome", "--channel", help="Playwright browser channel"),
    slow_mo: int = typer.Option(0, "--slow-mo", help="Playwright slow-motion delay in ms"),
    loops: int = typer.Option(1, "--loops", "-n", help="Run the scenario this many times"),
    pause_between_loops: float = typer.Option(
        0.0,
        "--pause-between-loops",
        help="Seconds to wait after each run before the next (ignored on last loop)",
    ),
):
    """Run a named click/type scenario with human-like behavior."""
    if loops < 1:
        console.print("[bold red]--loops must be at least 1[/bold red]")
        raise typer.Exit(1)

    try:
        get_scenario(scenario)
    except KeyError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(1) from exc

    if driver == Driver.nodriver:
        if not nodriver_available():
            console.print(
                "[bold red]Nodriver is not available on this Python version. "
                "Use --driver playwright (default) or Python 3.10–3.12 with nodriver installed.[/bold red]"
            )
            raise typer.Exit(1)
        console.print(
            "[bold red]Nodriver does not support JSON scenarios. Use --driver playwright.[/bold red]"
        )
        raise typer.Exit(1)

    runner = get_runner()
    runner.add_log_handler(lambda msg: console.print(msg))

    config = RunConfig(
        scenario=scenario,
        loops=loops,
        pause_between_loops_sec=pause_between_loops,
        headless=headless,
        channel=channel,
        slow_mo=slow_mo,
    )
    try:
        asyncio.run(runner.run_once(config))
    except Exception:
        raise typer.Exit(1) from None


@app.command("ui")
def ui(
    host: str = typer.Option("127.0.0.1", help="Bind address (local only recommended)"),
    port: int = typer.Option(8765, help="HTTP port"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open dashboard in browser"),
):
    """Launch the local web dashboard."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        console.print("[yellow]Warning: binding to non-localhost exposes the bot to your network.[/yellow]")

    url = f"http://{host}:{port}/"
    if open_browser:
        webbrowser.open(url)
    console.print(f"[green]Webbot UI[/green] at {url}")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")

    import uvicorn

    uvicorn.run("webbot.server:app", host=host, port=port, log_level="info")


@app.command()
def scenarios():
    """List available scenarios."""
    table = Table(title="Scenarios")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Description")
    for info in list_scenario_info():
        table.add_row(info.name, info.type, info.description)
    console.print(table)


@app.command()
def codegen(
    url: str = typer.Argument("about:blank", help="Starting URL for Playwright codegen"),
):
    """Launch Playwright's recorder to capture selectors for new scenarios."""
    profile = get_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "playwright",
        "codegen",
        "--browser",
        "chromium",
        url,
    ]
    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
    raise typer.Exit(subprocess.call(cmd))


@app.command("clear-profile")
def clear_profile(
    force: bool = typer.Option(False, "-f", "--force", help="Skip confirmation"),
):
    """Delete saved browser profile (cookies, local storage)."""
    profile = get_profile_dir()
    if not profile.exists():
        console.print("[dim]No profile to clear.[/dim]")
        return
    if not force and not typer.confirm(f"Delete profile at {profile}?"):
        raise typer.Abort()
    import shutil

    shutil.rmtree(profile)
    console.print("[green]Profile cleared.[/green]")


@app.command()
def version():
    """Show version and dependency status."""
    console.print(f"[bold]Webbot[/bold] v{__version__}")
    try:
        import playwright  # noqa: F401

        console.print("[green]Playwright:[/green] available")
    except ImportError:
        console.print("[red]Playwright:[/red] not installed")
    if nodriver_available():
        console.print("[green]Nodriver:[/green] available (stealth fallback)")
    else:
        console.print("[yellow]Nodriver:[/yellow] not available (optional stealth fallback)")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
