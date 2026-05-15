"""Shared scenario runner for CLI and web UI."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from webbot.browser import BrowserConfig, persistent_browser, save_failure_screenshot
from webbot.json_scenario import run_mixed_scenario_group
from webbot.run_context import RunContext, reset_run_context, set_run_context
from webbot.scenario_store import get_group_by_id, list_all_scenario_names
from webbot.scenarios import get_scenario


class RunState(str, Enum):
    idle = "idle"
    running = "running"
    stopped = "stopped"
    failed = "failed"
    completed = "completed"


@dataclass
class RunConfig:
    scenario: str | None = None
    group_id: str | None = None
    loops: int = 1
    pause_between_loops_sec: float = 0.0
    pause_between_flows_sec: float = 0.0
    headless: bool = False
    channel: str | None = "chrome"
    slow_mo: int = 0

    def __post_init__(self) -> None:
        sc = (self.scenario or "").strip()
        gid = (self.group_id or "").strip()
        if bool(sc) == bool(gid):
            raise ValueError("Exactly one of scenario or group_id must be set")
        self.scenario = sc or None
        self.group_id = gid or None


@dataclass
class RunStatus:
    state: RunState = RunState.idle
    scenario: str | None = None
    loop: int = 0
    loops: int = 0
    step: int = 0
    steps: int = 0
    step_label: str | None = None
    error: str | None = None
    step_progress: list[dict[str, Any]] = field(default_factory=list)


LogHandler = Callable[[str], None]
StatusHandler = Callable[[RunStatus], None]


class Runner:
    """Single active run; supports cancel and log subscribers."""

    def __init__(self) -> None:
        self._status = RunStatus()
        self._cancel = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._log_handlers: list[LogHandler] = []
        self._status_handlers: list[StatusHandler] = []
        self._lock = asyncio.Lock()
        self._run_context: RunContext | None = None

    @property
    def status(self) -> RunStatus:
        return self._status

    def add_log_handler(self, handler: LogHandler) -> None:
        self._log_handlers.append(handler)

    def add_status_handler(self, handler: StatusHandler) -> None:
        self._status_handlers.append(handler)

    def remove_log_handler(self, handler: LogHandler) -> None:
        if handler in self._log_handlers:
            self._log_handlers.remove(handler)

    def _log(self, message: str) -> None:
        for handler in self._log_handlers:
            try:
                handler(message)
            except Exception:
                pass

    def _notify_status(self) -> None:
        ctx = self._run_context
        if ctx:
            self._status.step = ctx.step
            self._status.steps = ctx.steps
            self._status.step_label = ctx.step_label
            self._status.loop = ctx.loop
            self._status.step_progress = ctx.step_progress_snapshot
        for handler in self._status_handlers:
            try:
                handler(self._status)
            except Exception:
                pass

    def _browser_config(self, config: RunConfig) -> BrowserConfig:
        return BrowserConfig(
            headless=config.headless,
            channel=config.channel or "chrome",
            slow_mo=config.slow_mo,
        )

    async def run_once(self, config: RunConfig) -> None:
        async with self._lock:
            if self._status.state == RunState.running:
                raise RuntimeError("A run is already in progress")
        self._cancel.clear()
        await self._execute(config)

    async def start(self, config: RunConfig) -> None:
        async with self._lock:
            if self._status.state == RunState.running:
                raise RuntimeError("A run is already in progress")
            self._cancel.clear()
            self._task = asyncio.create_task(self._execute(config))

    async def stop(self) -> None:
        self._cancel.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            if self._status.state == RunState.running:
                self._status.state = RunState.stopped
        self._log("Run stopped by user")
        self._notify_status()

    async def _execute(self, config: RunConfig) -> None:
        if config.group_id:
            group = get_group_by_id(config.group_id)
            names = [n.strip() for n in group.scenario_names if n.strip()]
            if not names:
                raise ValueError(f"Group '{config.group_id}' has no flows")
            available = set(list_all_scenario_names())
            for sn in names:
                if sn not in available:
                    raise ValueError(f"Group references unknown scenario '{sn}'")

            async def scenario_fn(page):
                await run_mixed_scenario_group(
                    page,
                    group_label=group.label,
                    scenario_names=names,
                    pause_between_flows_sec=config.pause_between_flows_sec,
                )

            label = f"group:{config.group_id}"
            log_start = f"Starting group '{label}' ({config.loops} loop(s))"
        else:
            scenario_fn = get_scenario(config.scenario or "")
            label = config.scenario or ""
            log_start = f"Starting scenario '{label}' ({config.loops} loop(s))"

        self._status = RunStatus(
            state=RunState.running,
            scenario=label,
            loop=0,
            loops=config.loops,
        )
        self._notify_status()
        self._log(log_start)

        self._run_context = RunContext(log=self._log, notify_status=self._notify_status)
        token = set_run_context(self._run_context)

        browser_cfg = self._browser_config(config)

        try:
            async with persistent_browser(browser_cfg) as (_context, page):
                for i in range(config.loops):
                    if self._cancel.is_set():
                        self._status.state = RunState.stopped
                        self._notify_status()
                        return

                    self._status.loop = i + 1
                    self._run_context.set_loop(i + 1, config.loops)
                    if config.loops > 1:
                        self._log(f"--- Loop {i + 1}/{config.loops} ---")

                    try:
                        await scenario_fn(page)
                    except Exception:
                        shot = await save_failure_screenshot(page, label)
                        if shot:
                            self._log(f"Screenshot saved: {shot}")
                        raise

                    if self._cancel.is_set():
                        self._status.state = RunState.stopped
                        self._notify_status()
                        return

                    if i < config.loops - 1 and config.pause_between_loops_sec > 0:
                        self._log(
                            f"Pausing {config.pause_between_loops_sec:.0f}s before next loop..."
                        )
                        try:
                            await asyncio.wait_for(
                                self._cancel.wait(),
                                timeout=config.pause_between_loops_sec,
                            )
                            self._status.state = RunState.stopped
                            self._notify_status()
                            return
                        except asyncio.TimeoutError:
                            pass

            self._status.state = RunState.completed
            self._log(f"Run '{label}' completed")
            self._notify_status()

        except asyncio.CancelledError:
            self._status.state = RunState.stopped
            self._log("Run cancelled")
            self._notify_status()
            raise
        except Exception as exc:
            self._status.state = RunState.failed
            self._status.error = str(exc)
            self._log(f"Error: {exc}")
            self._notify_status()
            raise
        finally:
            reset_run_context(token)
            self._run_context = None


_runner: Runner | None = None


def get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner()
    return _runner
