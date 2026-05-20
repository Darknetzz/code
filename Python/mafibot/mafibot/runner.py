"""Mafibot runner for CLI and web UI (single active browser task)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from playwright.async_api import BrowserContext, Page

from mafibot import brain
from mafibot.brain import get_last_idle_detail, get_last_parse_error
from mafibot.auth import ensure_session, is_logged_in
from mafibot.config import BotProfile, load_bot_profile
from mafibot.discover import run_discovery
from mafibot.preflight import run_preflight_checks
from mafibot.session import SessionConfig, mafia_session

log = logging.getLogger("mafibot.runner")


class RunnerState(str, Enum):
    idle = "idle"
    running = "running"
    login = "login"
    discover = "discover"
    stopped = "stopped"
    failed = "failed"
    completed = "completed"


def run_state_blocks_start(state: RunnerState) -> bool:
    return state in (RunnerState.running, RunnerState.login, RunnerState.discover)


@dataclass
class ActiveCooldownSnapshot:
    id: str
    label: str
    ready_at: str | None = None
    remaining_sec: float | None = None
    raw: str = ""


@dataclass
class ReportEntrySnapshot:
    username: str
    city: str | None = None
    null_delay: bool = False
    incoming_shot: bool = False


@dataclass
class GameStateSnapshot:
    logged_in: bool = False
    in_hotel: bool = False
    hotel_blocks_actions: bool = False
    money: int | None = None
    health_percent: int | None = None
    location: str | None = None
    crime_ready: bool = False
    crime_enkel_ready: bool = True
    crime_tung_ready: bool = True
    crime_stjel_ready: bool = True
    player_name: str | None = None
    attack: int | None = None
    protection: int | None = None
    rank_name: str | None = None
    happy_hour_active: bool = False
    happy_hour_buffs: list[str] = field(default_factory=list)
    mission_number: int | None = None
    mission_progress_current: int | None = None
    mission_progress_total: int | None = None
    mission_requirement_hint: str | None = None
    feriemodus: bool = False
    startbeskyttelse: bool = False
    kidnapped: bool = False
    family_war_active: bool = False
    minions_train_ready: bool = False
    report_entries: list[ReportEntrySnapshot] = field(default_factory=list)
    active_cooldowns: list[ActiveCooldownSnapshot] = field(default_factory=list)

    @classmethod
    def from_game_state(cls, state: Any) -> GameStateSnapshot:
        now = datetime.now()
        cooldowns: list[ActiveCooldownSnapshot] = []
        for cd in getattr(state, "active_cooldowns", ()) or ():
            ready_at = cd.ready_at
            ready_iso = ready_at.isoformat(timespec="seconds") if ready_at else None
            remaining: float | None = None
            if ready_at is not None:
                remaining = max(0.0, (ready_at - now).total_seconds())
            cooldowns.append(
                ActiveCooldownSnapshot(
                    id=cd.id,
                    label=cd.label,
                    ready_at=ready_iso,
                    remaining_sec=remaining,
                    raw=cd.raw,
                )
            )
        reports = [
            ReportEntrySnapshot(
                username=e.username,
                city=e.city,
                null_delay=e.null_delay,
                incoming_shot=e.incoming_shot,
            )
            for e in getattr(state, "report_entries", ()) or ()
        ]
        return cls(
            logged_in=state.logged_in,
            in_hotel=state.in_hotel,
            hotel_blocks_actions=state.hotel_blocks_actions,
            money=state.money,
            health_percent=state.health_percent,
            location=state.location,
            crime_ready=state.crime_ready,
            crime_enkel_ready=getattr(state, "crime_enkel_ready", state.crime_ready),
            crime_tung_ready=getattr(state, "crime_tung_ready", state.crime_ready),
            crime_stjel_ready=getattr(state, "crime_stjel_ready", state.crime_ready),
            attack=getattr(state, "attack", None),
            protection=getattr(state, "protection", None),
            rank_name=getattr(state, "rank_name", None),
            happy_hour_active=getattr(state, "happy_hour_active", False),
            happy_hour_buffs=list(getattr(state, "happy_hour_buffs", []) or []),
            mission_number=getattr(state, "mission_number", None),
            mission_progress_current=getattr(state, "mission_progress_current", None),
            mission_progress_total=getattr(state, "mission_progress_total", None),
            mission_requirement_hint=getattr(state, "mission_requirement_hint", None),
            feriemodus=getattr(state, "feriemodus", False),
            startbeskyttelse=getattr(state, "startbeskyttelse", False),
            kidnapped=getattr(state, "kidnapped", False),
            family_war_active=getattr(state, "family_war_active", False),
            minions_train_ready=getattr(state, "minions_train_ready", False),
            report_entries=reports,
            active_cooldowns=cooldowns,
        )


@dataclass
class MafibotStatus:
    state: RunnerState = RunnerState.idle
    profile: str | None = None
    dry_run: bool = False
    started_at: float | None = None
    last_action: str | None = None
    last_message: str | None = None
    last_reason: str | None = None
    parse_error: dict[str, str | None] | None = None
    error: str | None = None
    game: GameStateSnapshot = field(default_factory=GameStateSnapshot)

    def elapsed_sec(self) -> float | None:
        if self.started_at is None:
            return None
        return time.monotonic() - self.started_at


LogHandler = Callable[[str], None]
StatusHandler = Callable[[MafibotStatus], None]


class MafibotRunner:
    def __init__(self) -> None:
        self._status = MafibotStatus()
        self._cancel = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._log_handlers: list[LogHandler] = []
        self._status_handlers: list[StatusHandler] = []
        self._page: Page | None = None
        self._context: BrowserContext | None = None
        self._login_hold = False
        self._brain_status_hooked = False

    @property
    def status(self) -> MafibotStatus:
        return self._status

    @property
    def page(self) -> Page | None:
        return self._page

    def add_log_handler(self, handler: LogHandler) -> None:
        self._log_handlers.append(handler)

    def remove_log_handler(self, handler: LogHandler) -> None:
        if handler in self._log_handlers:
            self._log_handlers.remove(handler)

    def add_status_handler(self, handler: StatusHandler) -> None:
        self._status_handlers.append(handler)

    def _log(self, message: str) -> None:
        log.info(message)
        for h in self._log_handlers:
            try:
                h(message)
            except Exception:
                log.debug("log handler failed", exc_info=True)

    def _notify_status(self) -> None:
        idle = get_last_idle_detail()
        if idle and self._status.last_message and "nothing ready" in self._status.last_message:
            self._status.last_reason = idle
        parse_err = get_last_parse_error()
        if parse_err:
            self._status.parse_error = parse_err
        for h in self._status_handlers:
            try:
                h(self._status)
            except Exception:
                log.debug("status handler failed", exc_info=True)

    def _ensure_brain_hook(self) -> None:
        if self._brain_status_hooked:
            return

        def _on_brain_status(state, action_name, message, reason) -> None:
            self._status.game = GameStateSnapshot.from_game_state(state)
            if action_name:
                self._status.last_action = action_name
            self._status.last_message = message
            if reason:
                self._status.last_reason = reason
            self._notify_status()

        brain.add_status_callback(_on_brain_status)
        self._brain_status_hooked = True

    async def start_run(
        self,
        profile_name: str,
        *,
        max_minutes: int | None = None,
        dry_run: bool = False,
        accept_tos: bool = True,
        headless: bool = False,
        channel: str | None = "chrome",
        skip_preflight: bool = False,
        require_verification: bool = False,
    ) -> None:
        if not accept_tos:
            raise ValueError("accept_tos is required")
        if not skip_preflight:
            pf = run_preflight_checks(require_verification=require_verification)
            if not pf.ok:
                failed = [c.message for c in pf.checks if not c.ok]
                raise ValueError(f"Preflight failed: {'; '.join(failed)}")
        async with self._lock:
            if run_state_blocks_start(self._status.state):
                raise RuntimeError("A task is already in progress")
        self._ensure_brain_hook()
        self._cancel.clear()
        brain.clear_stop()
        profile = load_bot_profile(profile_name)
        self._status = MafibotStatus(
            state=RunnerState.running,
            profile=profile.name,
            dry_run=dry_run,
            started_at=time.monotonic(),
        )
        self._notify_status()
        self._task = asyncio.create_task(
            self._run_bot(profile, max_minutes=max_minutes, dry_run=dry_run, headless=headless, channel=channel)
        )

    async def start_login(
        self,
        *,
        timeout_sec: float = 600,
        headless: bool = False,
        channel: str | None = "chrome",
    ) -> None:
        async with self._lock:
            if run_state_blocks_start(self._status.state):
                raise RuntimeError("A task is already in progress")
        self._cancel.clear()
        self._login_hold = True
        self._status = MafibotStatus(state=RunnerState.login, started_at=time.monotonic())
        self._notify_status()
        self._task = asyncio.create_task(
            self._run_login(timeout_sec=timeout_sec, headless=headless, channel=channel)
        )

    async def start_discover(
        self,
        *,
        headless: bool = False,
        channel: str | None = "chrome",
        compare_last: bool = False,
    ) -> None:
        async with self._lock:
            if run_state_blocks_start(self._status.state):
                raise RuntimeError("A task is already in progress")
        self._ensure_brain_hook()
        self._cancel.clear()
        brain.clear_stop()
        self._status = MafibotStatus(state=RunnerState.discover, started_at=time.monotonic())
        self._notify_status()
        self._compare_last = compare_last
        self._task = asyncio.create_task(
            self._run_discover(headless=headless, channel=channel)
        )

    async def finish_login(self) -> None:
        self._login_hold = False
        self._cancel.set()

    async def stop(self) -> None:
        brain.request_stop()
        self._login_hold = False
        self._cancel.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._page = None
        self._context = None
        if self._status.state in (
            RunnerState.running,
            RunnerState.login,
            RunnerState.discover,
        ):
            self._status.state = RunnerState.stopped
        self._log("Stopped by user")
        self._notify_status()

    async def refresh_session_snapshot(self) -> GameStateSnapshot:
        from mafibot.state import parse_game_state

        if self._page is None:
            return self._status.game
        try:
            state = await parse_game_state(self._page)
            snap = GameStateSnapshot.from_game_state(state)
            self._status.game = snap
            self._notify_status()
            return snap
        except Exception as exc:
            self._log(f"Session parse failed: {exc}")
            if hasattr(exc, "to_dict"):
                self._status.parse_error = exc.to_dict()  # type: ignore[union-attr]
            return self._status.game

    async def _run_bot(
        self,
        profile: BotProfile,
        *,
        max_minutes: int | None,
        dry_run: bool,
        headless: bool,
        channel: str | None,
    ) -> None:
        cfg = SessionConfig(headless=headless, channel=channel)
        try:
            async with mafia_session(cfg) as (context, page):
                self._context = context
                self._page = page
                self._log(f"Starting autopilot profile={profile.name} dry_run={dry_run}")
                if not await is_logged_in(page):
                    self._log("Not logged in — waiting for session (run Login tab first)")
                    await ensure_session(page, manual=True)
                await brain.run_session(page, profile, max_minutes=max_minutes, dry_run=dry_run)
            if self._cancel.is_set():
                self._status.state = RunnerState.stopped
            else:
                self._status.state = RunnerState.completed
            self._log("Autopilot session finished")
        except asyncio.CancelledError:
            self._status.state = RunnerState.stopped
            self._log("Autopilot cancelled")
            raise
        except Exception as exc:
            self._status.state = RunnerState.failed
            self._status.error = str(exc)
            self._log(f"Autopilot failed: {exc}")
            raise
        finally:
            self._page = None
            self._context = None
            self._notify_status()

    async def _run_login(
        self,
        *,
        timeout_sec: float,
        headless: bool,
        channel: str | None,
    ) -> None:
        cfg = SessionConfig(headless=headless, channel=channel)
        try:
            async with mafia_session(cfg) as (context, page):
                self._context = context
                self._page = page
                self._log("Login browser open — sign in on mafiaspillet.no")
                state = await ensure_session(page, manual=True)
                self._status.game = GameStateSnapshot.from_game_state(state)
                self._notify_status()
                self._log("Login detected — browser stays open until you click Done in the UI")
                while self._login_hold and not self._cancel.is_set():
                    if await is_logged_in(page):
                        from mafibot.state import parse_game_state

                        try:
                            gs = await parse_game_state(page)
                            self._status.game = GameStateSnapshot.from_game_state(gs)
                            self._notify_status()
                        except Exception:
                            pass
                    await asyncio.sleep(2.0)
            self._status.state = RunnerState.completed
            self._log("Login browser closed")
        except asyncio.CancelledError:
            self._status.state = RunnerState.stopped
            raise
        except Exception as exc:
            self._status.state = RunnerState.failed
            self._status.error = str(exc)
            self._log(f"Login failed: {exc}")
            raise
        finally:
            self._page = None
            self._context = None
            self._notify_status()

    async def _run_discover(
        self,
        *,
        headless: bool,
        channel: str | None,
    ) -> None:
        cfg = SessionConfig(headless=headless, channel=channel)
        try:
            async with mafia_session(cfg) as (context, page):
                self._context = context
                self._page = page
                if not await is_logged_in(page):
                    await ensure_session(page, manual=True)
                compare = getattr(self, "_compare_last", False)
                out = await run_discovery(
                    page, manual_login=False, compare_last=compare
                )
                self._log(f"Discovery saved to {out}")
            self._status.state = RunnerState.completed
        except asyncio.CancelledError:
            self._status.state = RunnerState.stopped
            raise
        except Exception as exc:
            self._status.state = RunnerState.failed
            self._status.error = str(exc)
            self._log(f"Discovery failed: {exc}")
            raise
        finally:
            self._page = None
            self._context = None
            self._notify_status()


_runner: MafibotRunner | None = None


def get_runner() -> MafibotRunner:
    global _runner
    if _runner is None:
        _runner = MafibotRunner()
    return _runner
