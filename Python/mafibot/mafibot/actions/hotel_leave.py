"""Leave hotel so crimes and other actions are available."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, between_actions, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page, goto_sidebar
from mafibot.selectors import HOTEL_LEAVE_LABELS
from mafibot.state import GameState


class LeaveHotelAction:
    name = "leave_hotel"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop:
            return False
        return state.must_leave_hotel or (
            state.in_hotel and state.hotel_blocks_actions
        )

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        if dry_run:
            return ActionResult(True, "dry-run: would leave hotel")

        await goto_page(page, "crime", policy=policy)
        await page_reading_pause(page)

        clicked = await click_button_matching(page, HOTEL_LEAVE_LABELS, policy=policy)
        if not clicked:
            await goto_page(page, "hotel", policy=policy)
            await page_reading_pause(page)
            clicked = await click_button_matching(page, HOTEL_LEAVE_LABELS, policy=policy)
        if not clicked:
            await goto_sidebar(page, "hotel", policy=policy)
            clicked = await click_button_matching(page, ("sjekk ut", "forlat"), policy=policy)

        await between_actions(page, policy)
        if clicked:
            return ActionResult(True, "left hotel (or checkout clicked)")
        return ActionResult(False, "could not find leave-hotel control")
