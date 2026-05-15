#!/usr/bin/env python3
"""
Webbot - Human-like browser automation
Uses Playwright (with nodriver fallback) to click and type on web pages naturally.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from webbot import __version__
from webbot.browser import BrowserConfig, get_app_config_dir, get_profile_dir, persistent_browser, save_failure_screenshot
from webbot.nodriver_browser import nodriver_available, nodriver_browser
from webbot.scenarios import get_scenario, list_scenarios

console = Console()
app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)


class Driver(str, Enum):
    playwright = "playwright"
    nodriver = "nodriver"


def _browser_config(
    headless: bool,
    channel: Optional[str],
    slow_mo: int,
) -> BrowserConfig:
    return BrowserConfig(
        headless=headless,
        channel=channel or "chrome",
        slow_mo=slow_mo,
    )


async def _run_with_playwright(config: BrowserConfig, url: str | None, scenario_name: str | None) -> None:
    async with persistent_browser(config) as (_context, page):
        if url:
            await page.goto(url, wait_until="domcontentloaded")
            console.print(f"[green]Opened[/green] {url}")
            console.print("[dim]Close the browser window to exit.[/dim]")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                return

        if scenario_name:
            scenario = get_scenario(scenario_name)
            try:
                await scenario(page)
                console.print(f"[green]Scenario '{scenario_name}' completed.[/green]")
            except Exception as exc:
                shot = await save_failure_screenshot(page, scenario_name)
                if shot:
                    console.print(f"[yellow]Screenshot saved:[/yellow] {shot}")
                raise exc


async def _run_with_nodriver(config: BrowserConfig, url: str | None, scenario_name: str | None) -> None:
    async with nodriver_browser(config) as page:
        if url:
            await page.goto(url)
            console.print(f"[green]Opened[/green] {url} [dim](nodriver)[/dim]")
            console.print("[dim]Press Ctrl+C to exit.[/dim]")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                return

        if scenario_name:
            if scenario_name != "example":
                console.print(
                    "[yellow]Nodriver mode only supports the 'example' scenario for now. "
                    "Use --driver playwright for other scenarios.[/yellow]"
                )
            from webbot.scenarios.example_site import run as example_run

            try:
                await example_run(page)  # type: ignore[arg-type]
                console.print(f"[green]Scenario '{scenario_name}' completed.[/green]")
            except Exception as exc:
                screenshots = get_app_config_dir() / "screenshots"
                screenshots.mkdir(parents=True, exist_ok=True)
                path = screenshots / f"{scenario_name}-nodriver.png"
                await page.screenshot(str(path))
                console.print(f"[yellow]Screenshot saved:[/yellow] {path}")
                raise exc


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
    config = _browser_config(headless, channel, slow_mo)

    if driver == Driver.nodriver:
        if not nodriver_available():
            console.print(
                "[bold red]Nodriver is not available on this Python version. "
                "Use --driver playwright (default) or Python 3.10–3.12 with nodriver installed.[/bold red]"
            )
            raise typer.Exit(1)
        asyncio.run(_run_with_nodriver(config, url, None))
    else:
        asyncio.run(_run_with_playwright(config, url, None))


@app.command("run")
def run_scenario(
    scenario: str = typer.Argument(..., help="Scenario name to execute"),
    headless: bool = typer.Option(False, "--headless", help="Run without a visible window"),
    driver: Driver = typer.Option(Driver.playwright, "--driver", help="Browser backend"),
    channel: Optional[str] = typer.Option("chrome", "--channel", help="Playwright browser channel"),
    slow_mo: int = typer.Option(0, "--slow-mo", help="Playwright slow-motion delay in ms"),
):
    """Run a named click/type scenario with human-like behavior."""
    config = _browser_config(headless, channel, slow_mo)

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
        asyncio.run(_run_with_nodriver(config, None, scenario))
    else:
        asyncio.run(_run_with_playwright(config, None, scenario))


@app.command()
def scenarios():
    """List available scenarios."""
    table = Table(title="Scenarios")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_row("example", "Browse example.com with human-like clicks")
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
