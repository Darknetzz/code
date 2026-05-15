"""Per-step progress reporting during scenario runs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, Literal, TypeVar

from webbot.exceptions import WorkflowExit

T = TypeVar("T")

StepStatus = Literal["pending", "running", "ok", "failed", "skipped"]

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
        self.step_progress: list[dict[str, Any]] = []
        self._planned = False

    @property
    def step_progress_snapshot(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.step_progress]

    def plan_steps(self, items: list[tuple[int, str]]) -> None:
        self._planned = True
        self.step_progress = [
            {"index": index, "label": label, "status": "pending", "error": None}
            for index, label in items
        ]
        self.steps = len(items)
        self.step = 0
        self.step_label = None
        self._notify_status()

    def set_loop(self, loop: int, loops: int) -> None:
        self.loop = loop
        self.loops = loops
        self.step = 0
        self.step_label = None
        if self._planned:
            for item in self.step_progress:
                item["status"] = "pending"
                item["error"] = None
        else:
            self.step_progress = []
            self.steps = 0
        self._notify_status()

    def _get_step(self, index: int) -> dict[str, Any] | None:
        for item in self.step_progress:
            if item["index"] == index:
                return item
        return None

    def _ensure_step(self, index: int, label: str) -> dict[str, Any]:
        item = self._get_step(index)
        if item is None:
            item = {"index": index, "label": label, "status": "pending", "error": None}
            self.step_progress.append(item)
            self.step_progress.sort(key=lambda s: s["index"])
        else:
            item["label"] = label
        return item

    def begin_step(self, index: int, total: int, label: str) -> None:
        self.step = index
        self.steps = total
        self.step_label = label
        entry = self._ensure_step(index, label)
        entry["status"] = "running"
        entry["error"] = None
        loop_part = f"loop {self.loop}/{self.loops} · " if self.loops > 1 else ""
        self._log(f"[..] {loop_part}step {index}/{total}: {label}")
        self._notify_status()

    def complete_step(self, index: int, total: int, label: str) -> None:
        entry = self._ensure_step(index, label)
        entry["status"] = "ok"
        entry["error"] = None
        loop_part = f"loop {self.loop}/{self.loops} · " if self.loops > 1 else ""
        self._log(f"[OK] {loop_part}step {index}/{total}: {label}")
        self._notify_status()

    def fail_step(self, index: int, total: int, label: str, error: str) -> None:
        entry = self._ensure_step(index, label)
        entry["status"] = "failed"
        entry["error"] = error
        loop_part = f"loop {self.loop}/{self.loops} · " if self.loops > 1 else ""
        self._log(f"[FAIL] {loop_part}step {index}/{total}: {label} - {error}")
        self._notify_status()

    def skip_step(self, index: int, total: int, label: str) -> None:
        entry = self._ensure_step(index, label)
        entry["status"] = "skipped"
        entry["error"] = None
        loop_part = f"loop {self.loop}/{self.loops} · " if self.loops > 1 else ""
        self._log(f"[SKIP] {loop_part}step {index}/{total}: {label}")
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
    except WorkflowExit:
        if ctx:
            ctx.complete_step(index, total, label)
        raise
    except Exception as exc:
        if ctx:
            ctx.fail_step(index, total, label, str(exc))
        raise
