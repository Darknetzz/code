"""Book / check in to hotel — default home between actions."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.hotel_stay import hotel_booking_blocked_reason, should_skip_booking
from mafibot.state import parse_hotel_booking_hint
from mafibot.human_policy import HumanPolicy, human_delay, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page, goto_sidebar
from mafibot.selectors import HOTEL_BOOK_LABELS
from mafibot.state import GameState, parse_game_state


class BookHotelAction:
    name = "book_hotel"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if state.needs_stop or state.in_jail:
            return False
        if not profile.stay_in_hotel:
            return False
        if hotel_booking_blocked_reason(state, profile):
            return False
        return not should_skip_booking(state)

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
        quick: bool = False,
    ) -> ActionResult:
        if dry_run:
            return ActionResult(True, "dry-run: would book hotel")

        fresh = await parse_game_state(page)
        if should_skip_booking(fresh):
            return ActionResult(True, "already in hotel")

        await goto_page(page, "hotel", policy=policy)
        if quick:
            await human_delay(0.25, 0.8, distribution="uniform")
        else:
            await page_reading_pause(page)

        clicked = await click_button_matching(
            page,
            HOTEL_BOOK_LABELS + ("sjekk inn på", "hotell", "overnatt"),
            policy=policy,
        )
        if not clicked:
            await goto_sidebar(page, "hotel", policy=policy)
            clicked = await click_button_matching(page, HOTEL_BOOK_LABELS, policy=policy)

        if not quick:
            await human_delay(0.3, 1.0)
        after = await parse_game_state(page)
        hint = parse_hotel_booking_hint(after.page_text_sample)
        if hint:
            return ActionResult(False, f"hotel book blocked: {hint}")
        if should_skip_booking(after) or clicked:
            return ActionResult(True, "booked hotel or check-in clicked")
        return ActionResult(False, "could not find hotel book/check-in control")
