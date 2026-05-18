"""Mouse trail across paced clicks."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mafibot.human_policy import HumanPolicy, human_click_paced, reset_mouse_position


@pytest.mark.asyncio
async def test_mouse_position_carried_between_clicks():
    reset_mouse_position()
    page = AsyncMock()
    loc1 = AsyncMock()
    loc1.bounding_box = AsyncMock(return_value={"x": 10, "y": 20, "width": 100, "height": 40})
    loc2 = AsyncMock()
    loc2.bounding_box = AsyncMock(return_value={"x": 200, "y": 300, "width": 80, "height": 30})
    loc1.scroll_into_view_if_needed = AsyncMock()
    loc2.scroll_into_view_if_needed = AsyncMock()

    starts: list[tuple[float, float] | None] = []

    async def capture_move(page, x, y, *, start=None):
        starts.append(start)
        return None

    with patch("mafibot.human_policy.random.random", return_value=0.99):
        with patch("mafibot.human_policy.move_mouse_human", side_effect=capture_move):
            with patch("mafibot.human_policy._enforce_click_gap", new_callable=AsyncMock):
                with patch("mafibot.human_policy.maybe_think_pause", new_callable=AsyncMock):
                    with patch("mafibot.human_policy.maybe_scroll_page", new_callable=AsyncMock):
                        with patch("mafibot.human_policy.reading_pause", new_callable=AsyncMock):
                            with patch("mafibot.human_policy.human_delay", new_callable=AsyncMock):
                                with patch(
                                    "mafibot.human_policy.idle_mouse_drift",
                                    new_callable=AsyncMock,
                                ):
                                    await human_click_paced(page, loc1, HumanPolicy())
                                    await human_click_paced(page, loc2, HumanPolicy())

    assert starts[0] is None
    assert starts[1] is not None
