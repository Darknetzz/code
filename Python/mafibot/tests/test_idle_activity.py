"""Chunked idle waits with micro-activity."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from mafibot.human_policy import HumanPolicy, sleep_with_idle_activity


@pytest.mark.asyncio
async def test_sleep_with_idle_activity_respects_duration():
    page = AsyncMock()
    with patch("mafibot.human_policy._idle_micro_activity", new_callable=AsyncMock):
        start = time.monotonic()
        ok = await sleep_with_idle_activity(page, 12.0, HumanPolicy())
        elapsed = time.monotonic() - start
    assert ok is True
    assert 10.0 <= elapsed <= 16.0


@pytest.mark.asyncio
async def test_sleep_with_idle_activity_cancelled():
    page = AsyncMock()
    cancel = asyncio.Event()
    cancel.set()
    ok = await sleep_with_idle_activity(page, 30.0, HumanPolicy(), cancel=cancel)
    assert ok is False


@pytest.mark.asyncio
async def test_idle_micro_activity_calls_drift():
    page = AsyncMock()
    with patch("mafibot.human_policy.random.random", return_value=0.1):
        with patch(
            "mafibot.human_policy.idle_mouse_drift", new_callable=AsyncMock
        ) as drift:
            from mafibot.human_policy import _idle_micro_activity

            await _idle_micro_activity(page, HumanPolicy())
    drift.assert_awaited_once()
