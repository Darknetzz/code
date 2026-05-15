"""Shared scenario runner for CLI and web UI."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from webbot.browser import BrowserConfig, persistent_browser, save_failure_screenshot
from webbot.scenarios import get_scenario


class RunState(str, Enum):
    idle = "idle"
    running = "running"
    stopped = "stopped"
    failed = "failed"
    completed = "completed"


@dataclass
class RunConfig:
    scenario: str
    loops: int = 1
    pause_between_loops_sec: float = 0.0
    headless: bool = False
    channel: str | None = "chrome"
    slow_mo: int = 0


@dataclass
class RunStatus:
    state: RunState = RunState.idle
    scenario: str | None = None
    loop: int = 0
    loops: int = 0
    error: str | None = None


LogHandler = Callable[[str], None]


class Runner:
    """Single active run; supports cancel and log subscribers."""

    def __init__(self) -> None:
        self._status = RunStatus()
        self._cancel = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._log_handlers: list[LogHandler] = []
        self._lock = asyncio.Lock()

    @property
    def status(self) -> RunStatus:
        return self._status

    def add_log_handler(self, handler: LogHandler) -> None:
        self._log_handlers.append(handler)

    def remove_log_handler(self, handler: LogHandler) -> None:
        if handler in self._log_handlers:
            self._log_handlers.remove(handler)

    def _log(self, message: str) -> None:
        for handler in self._log_handlers:
            try:
                handler(message)
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

    async def _execute(self, config: RunConfig) -> None:
        self._status = RunStatus(
            state=RunState.running,
            scenario=config.scenario,
            loop=0,
            loops=config.loops,
        )
        self._log(f"Starting scenario '{config.scenario}' ({config.loops} loop(s))")

        browser_cfg = self._browser_config(config)
        scenario_fn = get_scenario(config.scenario)

        try:
            async with persistent_browser(browser_cfg) as (_context, page):
                for i in range(config.loops):
                    if self._cancel.is_set():
                        self._status.state = RunState.stopped
                        return

                    self._status.loop = i + 1
                    if config.loops > 1:
                        self._log(f"Loop {i + 1}/{config.loops}")

                    try:
                        await scenario_fn(page)
                    except Exception:
                        shot = await save_failure_screenshot(page, config.scenario)
                        if shot:
                            self._log(f"Screenshot saved: {shot}")
                        raise

                    if self._cancel.is_set():
                        self._status.state = RunState.stopped
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
                            return
                        except asyncio.TimeoutError:
                            pass

            self._status.state = RunState.completed
            self._log(f"Scenario '{config.scenario}' completed")

        except asyncio.CancelledError:
            self._status.state = RunState.stopped
            self._log("Run cancelled")
            raise
        except Exception as exc:
            self._status.state = RunState.failed
            self._status.error = str(exc)
            self._log(f"Error: {exc}")
            raise


_runner: Runner | None = None


def get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner()
    return _runner
