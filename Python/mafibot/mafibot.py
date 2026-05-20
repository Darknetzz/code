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
from mafibot.fixtures import promote_discovery_fixtures
from mafibot.preflight import run_preflight_checks
from mafibot.verify_pages import run_verification, verification_exit_code
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
    from mafibot.session_log import configure_session_file_logging

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    configure_session_file_logging()


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


@app.command("check")
def check_cmd(
    require_verification: bool = typer.Option(
        False,
        "--require-verification",
        help="Fail if latest discovery verification did not pass",
    ),
) -> None:
    """Pre-flight: config dir, pages.json, discovery verification."""
    _setup_logging(False)
    try:
        import playwright  # noqa: F401

        console.print("[green]playwright[/green] installed")
    except ImportError:
        console.print("[red]playwright not installed[/red]")
        raise typer.Exit(1) from None

    result = run_preflight_checks(require_verification=require_verification)
    for check in result.checks:
        mark = "[green]ok[/green]" if check.ok else "[red]fail[/red]"
        console.print(f"  {mark} {check.id}: {check.message}")
        if check.hint and not check.ok:
            console.print(f"       [dim]{check.hint}[/dim]")
    for warning in result.warnings:
        console.print(f"  [yellow]warn[/yellow] {warning}")
    if not result.ok:
        raise typer.Exit(1)
    console.print("[green]All checks passed.[/green]")


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
    compare_last: bool = typer.Option(
        False,
        "--compare-last",
        help="Print HTML diffs vs the previous discovery run",
    ),
) -> None:
    """Map ?side= links and save HTML/screenshots (requires login)."""
    _require_tos(accept_tos)
    _setup_logging(True)

    async def _main() -> None:
        async with mafia_session(SessionConfig(headless=headless)) as (_ctx, page):
            path = await run_discovery(
                page,
                manual_login=not headless,
                compare_last=compare_last,
            )
            console.print(f"Done: {path}")

    asyncio.run(_main())


@app.command("verify-pages")
def verify_pages(
    discovery_dir: Path | None = typer.Option(
        None,
        "--discovery-dir",
        help="Path to a discovery run folder (default: latest)",
    ),
) -> None:
    """Audit discovery HTML against selectors and crime_catalog labels."""
    _setup_logging(False)
    try:
        report_path, audits = run_verification(discovery_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    fail_count = sum(len(a.failed) for a in audits)
    missing = sum(1 for a in audits if a.html_path is None)
    console.print(f"Report: {report_path}")
    console.print(f"Pages: {len(audits)}, missing HTML: {missing}, failed checks: {fail_count}")
    if verification_exit_code(audits) != 0:
        raise typer.Exit(1)


@app.command("promote-fixtures")
def promote_fixtures_cmd(
    discovery_dir: Path | None = typer.Option(
        None,
        "--discovery-dir",
        help="Discovery run folder (default: latest)",
    ),
) -> None:
    """Copy latest discovery HTML into tests/fixtures/discovered (redacted)."""
    _setup_logging(False)
    try:
        dest, copied = promote_discovery_fixtures(discovery_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Promoted {len(copied)} pages to[/green] {dest}")
    console.print("[dim]Run: python -m pytest tests/ -q[/dim]")


@app.command()
def run(
    profile: str = typer.Option("ranker", "--profile", "-p"),
    max_minutes: int = typer.Option(120, "--max-minutes"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log decisions without clicking"),
    accept_tos: bool = typer.Option(False, "--accept-tos"),
    headless: bool = typer.Option(False, "--headless"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    skip_preflight: bool = typer.Option(False, "--skip-preflight"),
    require_verification: bool = typer.Option(
        False,
        "--require-verification",
        help="Require passing verify-pages on latest discovery",
    ),
) -> None:
    """Run autopilot session."""
    _require_tos(accept_tos)
    _setup_logging(verbose)
    if not skip_preflight:
        pf = run_preflight_checks(require_verification=require_verification)
        if not pf.ok:
            for check in pf.checks:
                if not check.ok:
                    console.print(f"[red]Preflight {check.id}:[/red] {check.message}")
            raise typer.Exit(1)
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


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8766, "--port"),
    insecure_bind: bool = typer.Option(
        False,
        "--insecure-bind",
        help="Allow binding to non-loopback addresses (not recommended)",
    ),
) -> None:
    """Start local web dashboard (Run / Config / Login)."""
    if host not in ("127.0.0.1", "localhost", "::1") and not insecure_bind:
        console.print(
            "[red]Refusing to bind to non-loopback host. "
            "Use --insecure-bind if you understand the risk.[/red]"
        )
        raise typer.Exit(1)
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Install UI deps: pip install fastapi uvicorn[standard][/red]")
        raise typer.Exit(1) from None
    token = __import__("os").getenv("MAFIBOT_UI_TOKEN", "").strip()
    if token:
        console.print("[dim]UI token auth enabled (MAFIBOT_UI_TOKEN).[/dim]")
    elif host in ("127.0.0.1", "localhost", "::1"):
        console.print(
            "[yellow]MAFIBOT_UI_TOKEN is not set — API is open on localhost.[/yellow]"
        )
    console.print(f"Mafibot UI: http://{host}:{port}/")
    console.print("[dim]Localhost only — do not expose without auth.[/dim]")
    uvicorn.run("mafibot.server:app", host=host, port=port, reload=False)


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
