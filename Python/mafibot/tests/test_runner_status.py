"""Runner status and concurrency guards."""

from __future__ import annotations

import asyncio

import pytest

from datetime import datetime, timedelta

from mafibot.models import RunStatusResponse
from mafibot.runner import (
    MafibotRunner,
    MafibotStatus,
    RunnerState,
    run_state_blocks_start,
)
from mafibot.state import ActionCooldown, GameState
from mafibot.server import _status_response


def test_run_state_blocks_start():
    assert run_state_blocks_start(RunnerState.running)
    assert run_state_blocks_start(RunnerState.login)
    assert not run_state_blocks_start(RunnerState.idle)
    assert not run_state_blocks_start(RunnerState.completed)


def test_status_serialization():
    runner = MafibotRunner()
    runner._status = MafibotStatus(
        state=RunnerState.running,
        profile="ranker",
        dry_run=True,
        started_at=0.0,
        last_action="crime",
        last_message="picked",
    )
    resp = _status_response(runner)
    data = RunStatusResponse.model_validate(resp.model_dump())
    assert data.state == "running"
    assert data.profile == "ranker"
    assert data.dry_run is True
    assert data.last_action == "crime"


def test_status_includes_active_cooldowns():
    from mafibot.runner import GameStateSnapshot

    ready_at = datetime.now() + timedelta(minutes=5)
    snap = GameStateSnapshot.from_game_state(
        GameState(
            crime_ready=False,
            active_cooldowns=[
                ActionCooldown(id="crime", label="Crime", ready_at=ready_at, raw="5 min")
            ],
        )
    )
    assert len(snap.active_cooldowns) == 1
    assert snap.active_cooldowns[0].id == "crime"
    assert snap.active_cooldowns[0].remaining_sec is not None
    assert snap.active_cooldowns[0].remaining_sec > 0


@pytest.mark.asyncio
async def test_start_blocked_when_running(monkeypatch):
    runner = MafibotRunner()
    runner._status.state = RunnerState.running

    async def noop(*_a, **_k):
        await asyncio.sleep(10)

    monkeypatch.setattr(runner, "_run_bot", noop)
    with pytest.raises(RuntimeError, match="already in progress"):
        await runner.start_run("ranker", accept_tos=True)
