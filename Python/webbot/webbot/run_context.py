"""Per-step progress reporting during scenario runs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import TypeVar

T = TypeVar("T")

_current: ContextVar[RunContext | None] = ContextVar("webbot_run_context", default=None)


class RunContext:
    """Tracks and logs each step in the active run (loop + step progress)."""

    def __init__(self, *, log: Callable[[str], None], notify_status: Callable[[], None]) -> None:
        self._log = log
        self._notify_status = notify_status
        self.loop = 0
        self.loops = 0
        self.step = 0
        self.steps = 0
        self.step_label: str | None = None

    def set_loop(self, loop: int, loops: int) -> None:
        self.loop = loop
        self.loops = loops
        self.step = 0
        self.steps = 0
        self.step_label = None
        self._notify_status()

    def begin_step(self, index: int, total: int, label: str) -> None:
        self.step = index
        self.steps = total
        self.step_label = label
        loop_part = f"loop {self.loop}/{self.loops} · " if self.loops > 1 else ""
        self._log(f"→ {loop_part}step {index}/{total}: {label}")
        self._notify_status()

    def complete_step(self, index: int, total: int, label: str) -> None:
        loop_part = f"loop {self.loop}/{self.loops} · " if self.loops > 1 else ""
        self._log(f"✓ {loop_part}step {index}/{total}: {label}")
        self._notify_status()

    def fail_step(self, index: int, total: int, label: str, error: str) -> None:
        loop_part = f"loop {self.loop}/{self.loops} · " if self.loops > 1 else ""
        self._log(f"✗ {loop_part}step {index}/{total}: {label} — {error}")
        self._notify_status()


def get_run_context() -> RunContext | None:
    return _current.get()


def set_run_context(ctx: RunContext | None) -> object:
    return _current.set(ctx)


def reset_run_context(token: object) -> None:
    _current.reset(token)


async def run_verified_step(
    index: int,
    total: int,
    label: str,
    fn: Callable[[], Awaitable[None]],
) -> None:
    """Run one step with begin/complete/fail logging when a run context is active."""
    ctx = get_run_context()
    if ctx:
        ctx.begin_step(index, total, label)
    try:
        await fn()
        if ctx:
            ctx.complete_step(index, total, label)
    except Exception as exc:
        if ctx:
            ctx.fail_step(index, total, label, str(exc))
        raise
