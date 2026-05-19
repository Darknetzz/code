"""Combat / murder — static targets, report stream, retaliate."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.action_targets import murder_target_city, murder_target_names, pick_murder_target
from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.page_actions import fill_murder_target
from mafibot.profile_options import gameplay_paused
from mafibot.report_stream import pick_report_stream_target
from mafibot.selectors import MURDER_ACTION_LABELS
from mafibot.state import GameState, parse_game_state


class MurderAction:
    name = "murder"

    def _has_target(self, state: GameState, profile: BotProfile) -> bool:
        if profile.murder_mode != "static_targets":
            if pick_report_stream_target(state, profile):
                return True
        return bool(murder_target_names(profile))

    def _retaliate_available(self, state: GameState, profile: BotProfile) -> bool:
        if profile.murder_mode != "retaliate_only":
            return True
        return any(entry.incoming_shot for entry in state.report_entries)

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if gameplay_paused(profile, state):
            return False
        if not profile.combat_enabled:
            return False
        if not self._has_target(state, profile):
            return False
        if not self._retaliate_available(state, profile):
            return False
        if state.needs_stop or state.in_jail or state.in_hospital:
            return False
        if state.startbeskyttelse:
            return False
        if profile.aggression < 0.5 and profile.murder_mode == "static_targets":
            return False
        if state.low_health_for_profile(profile.min_health_percent):
            return False
        if not state.murder_ready:
            return False
        return True

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        target = pick_murder_target(profile, state)
        if not target:
            return ActionResult(False, "murder: no target")

        dest_city = murder_target_city(profile, state)
        if (
            profile.murder_travel_before_shoot
            and dest_city
            and state.location
            and dest_city.lower() != state.location.lower()
            and state.travel_ready
        ):
            from mafibot.actions.travel import TravelAction

            travel = TravelAction()
            saved_dests = list(profile.travel_destinations)
            profile.travel_destinations = [dest_city]
            try:
                if dry_run:
                    return ActionResult(
                        True,
                        f"dry-run: would travel to {dest_city} then shoot {target}",
                    )
                tr = await travel.run(page, state, profile, policy, dry_run=False)
                if not tr.success:
                    return ActionResult(
                        False,
                        f"murder: travel to {dest_city} failed: {tr.message}",
                    )
                state = await parse_game_state(page)
            finally:
                profile.travel_destinations = saved_dests

        if dry_run:
            return ActionResult(True, f"dry-run: would target {target}")

        await goto_page(page, "murder", policy=policy)
        await page_reading_pause(page)

        if not await fill_murder_target(page, target, policy=policy, dry_run=False):
            return ActionResult(False, f"murder: could not fill target field for {target}")

        if not profile.murder_actually_shoot:
            return ActionResult(True, f"murder: filled {target}; shoot disabled in profile")

        if profile.aggression < 0.85 and profile.murder_mode == "static_targets":
            return ActionResult(True, f"murder: filled {target}; skipped shot (aggression)")

        clicked = await click_button_matching(page, MURDER_ACTION_LABELS, policy=policy)
        if clicked:
            return ActionResult(True, f"murder submitted vs {target}")
        return ActionResult(False, f"murder: no shoot button after targeting {target}")
