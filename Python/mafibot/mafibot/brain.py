"""Autopilot decision loop — hotel-first, slow human-paced."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from datetime import datetime, timedelta
from playwright.async_api import Page

from mafibot.actions.base import Action, ActionResult, action_by_name, all_actions
from mafibot.actions.hotel_book import BookHotelAction
from mafibot.actions.hotel_leave import LeaveHotelAction
from mafibot.config import BotProfile, in_play_window
from mafibot.hotel_stay import action_requires_leave_hotel
from mafibot.human_policy import (
    HumanPolicy,
    between_actions,
    cycle_wait_after_action,
    cycle_wait_nothing_todo,
    hotel_transition_policy,
    idle_break_seconds,
    page_reading_pause,
    pause_before_book_hotel,
    sleep_wait,
)
from mafibot.navigation import ensure_game_shell
from mafibot.session import capture_failure
from mafibot.state import GameState, ParseError, parse_game_state

log = logging.getLogger("mafibot")

_cancel = asyncio.Event()
_ROTATION_EXCLUDE = frozenset({"leave_hotel", "book_hotel", "hotel"})

StatusCallback = Callable[["GameState", str | None, str, str | None], None]
_status_callbacks: list[StatusCallback] = []


def add_status_callback(handler: StatusCallback) -> None:
    _status_callbacks.append(handler)


def remove_status_callback(handler: StatusCallback) -> None:
    if handler in _status_callbacks:
        _status_callbacks.remove(handler)


def _notify_status(
    state: GameState,
    action_name: str | None,
    message: str,
    reason: str | None = None,
) -> None:
    for handler in list(_status_callbacks):
        try:
            handler(state, action_name, message, reason)
        except Exception:
            pass


def request_stop() -> None:
    _cancel.set()


def clear_stop() -> None:
    _cancel.clear()


def is_stop_requested() -> bool:
    return _cancel.is_set()


def _policy_from_profile(profile: BotProfile) -> HumanPolicy:
    return HumanPolicy(
        jitter_min_sec=profile.cooldown_jitter_min_sec,
        jitter_max_sec=profile.cooldown_jitter_max_sec,
        min_seconds_between_clicks=profile.min_seconds_between_clicks,
        min_seconds_after_tab_change=profile.min_seconds_after_tab_change,
        post_action_wait_min_sec=profile.post_action_wait_min_sec,
        post_action_wait_max_sec=profile.post_action_wait_max_sec,
        nothing_todo_wait_min_sec=profile.nothing_todo_wait_min_sec,
        nothing_todo_wait_max_sec=profile.nothing_todo_wait_max_sec,
    )


def _ordered_action_names(profile: BotProfile) -> list[str]:
    """Priority list from profile.economy_order plus legacy social/combat flags."""
    order: list[str] = []
    for name in profile.economy_order:
        if name in _ROTATION_EXCLUDE:
            continue
        if name not in order:
            order.append(name)
    if profile.social_enabled:
        for s in ("messages", "family"):
            if s not in order:
                order.append(s)
    if profile.combat_enabled and "murder" not in order:
        order.append("murder")
    normalized: list[str] = []
    for n in order:
        if n == "work":
            n = "business"
        if n not in normalized:
            normalized.append(n)
    return normalized


async def _book_hotel(
    page: Page,
    profile: BotProfile,
    policy: HumanPolicy,
    *,
    dry_run: bool = False,
    quick: bool = False,
) -> ActionResult:
    book = BookHotelAction()
    state = await parse_game_state(page)
    if not await book.can_run(state, profile):
        return ActionResult(True, "skip book: already in hotel")
    book_policy = hotel_transition_policy(policy) if quick else policy
    return await book.run(page, state, profile, book_policy, dry_run=dry_run, quick=quick)


async def _leave_hotel_if_needed(
    page: Page,
    profile: BotProfile,
    policy: HumanPolicy,
    *,
    dry_run: bool = False,
) -> ActionResult | None:
    leave = LeaveHotelAction()
    state = await parse_game_state(page)
    if not await leave.can_run(state, profile):
        return None
    return await leave.run(page, state, profile, policy, dry_run=dry_run)


async def execute_with_hotel_stay(
    page: Page,
    action: Action,
    profile: BotProfile,
    policy: HumanPolicy,
    *,
    dry_run: bool = False,
) -> ActionResult:
    """Book → (leave if needed) → action → book again."""
    state = await parse_game_state(page)

    if profile.stay_in_hotel and profile.book_hotel_before_action:
        pre = await _book_hotel(page, profile, policy, dry_run=dry_run)
        log.info("pre-action book: %s", pre.message)
        state = await parse_game_state(page)

    if profile.stay_in_hotel and action_requires_leave_hotel(action.name):
        left = await _leave_hotel_if_needed(page, profile, policy, dry_run=dry_run)
        if left:
            log.info("leave for %s: %s", action.name, left.message)
        state = await parse_game_state(page)

    result = await action.run(page, state, profile, policy, dry_run=dry_run)

    if profile.stay_in_hotel and profile.book_hotel_after_every_action and not dry_run:
        gap = await pause_before_book_hotel(profile.max_seconds_before_book_hotel)
        log.info("pause before book: %.2fs (max %.2fs)", gap, profile.max_seconds_before_book_hotel)
        post = await _book_hotel(page, profile, policy, dry_run=False, quick=True)
        log.info("post-action book: %s", post.message)

    return result


async def pick_next_action(
    state: GameState,
    profile: BotProfile,
    *,
    dry_run: bool = False,
) -> tuple[Action | None, str]:
    if state.needs_stop:
        return None, "stop: captcha, ban, or logged out"

    if state.in_jail:
        return None, "idle: in jail"

    for name in _ordered_action_names(profile):
        action = action_by_name(name)
        if action is None:
            continue
        if await action.can_run(state, profile):
            hint = " (will leave hotel first)" if (
                profile.stay_in_hotel and action_requires_leave_hotel(name) and state.in_hotel
            ) else ""
            return action, f"selected: {name}{hint}"

    allowed = set(_ordered_action_names(profile))
    for action in all_actions():
        if action.name in _ROTATION_EXCLUDE or action.name not in allowed:
            continue
        if await action.can_run(state, profile):
            return action, f"fallback: {action.name}"

    return None, "nothing ready"


async def run_once(
    page: Page,
    profile: BotProfile,
    *,
    dry_run: bool = False,
) -> ActionResult | None:
    policy = _policy_from_profile(profile)
    try:
        await ensure_game_shell(page, policy)
        state = await parse_game_state(page)
    except ParseError as exc:
        log.error("parse failed: %s", exc)
        await capture_failure(page, "parse_error")
        return None

    if state.needs_stop:
        log.warning(
            "session stop: captcha=%s banned=%s login=%s",
            state.captcha,
            state.banned,
            state.on_login_page,
        )
        return None

    action, reason = await pick_next_action(state, profile, dry_run=dry_run)
    log.info("decision: %s", reason)
    _notify_status(
        state,
        action.name if action else None,
        reason,
        reason,
    )
    if action is None:
        if profile.stay_in_hotel and profile.book_hotel_when_idle and not dry_run:
            await _book_hotel(page, profile, policy)
        return None

    if dry_run:
        log.info("dry-run: %s (hotel wrap simulated)", action.name)
        return ActionResult(True, f"dry-run: {action.name}")

    result = await execute_with_hotel_stay(page, action, profile, policy, dry_run=False)
    log.info("action %s: success=%s msg=%s", action.name, result.success, result.message)
    try:
        after_state = await parse_game_state(page)
    except ParseError:
        after_state = state
    _notify_status(
        after_state,
        action.name,
        result.message,
        f"done: {action.name}",
    )
    await page_reading_pause(page)
    await between_actions(page, policy)
    return result


async def run_session(
    page: Page,
    profile: BotProfile,
    *,
    max_minutes: int | None = None,
    dry_run: bool = False,
) -> None:
    clear_stop()
    policy = _policy_from_profile(profile)
    limit = max_minutes if max_minutes is not None else profile.max_session_minutes
    deadline = datetime.now() + timedelta(minutes=limit)
    session_start = datetime.now()

    if profile.stay_in_hotel and not dry_run:
        await ensure_game_shell(page, policy)
        await _book_hotel(page, profile, policy)
        log.info("session start: ensured hotel check-in")

    while datetime.now() < deadline and not is_stop_requested():
        if not in_play_window(profile):
            log.info("outside play window — sleeping 10 min")
            await asyncio.sleep(600)
            continue

        if random.random() < profile.idle_chance:
            idle_sec = idle_break_seconds(profile.idle_min_minutes, profile.idle_max_minutes)
            log.info("idle break %.2f min (human AFK)", idle_sec / 60.0)
            await asyncio.sleep(idle_sec)
            continue

        try:
            result = await run_once(page, profile, dry_run=dry_run)
        except Exception:
            log.exception("run_once failed")
            await capture_failure(page, "run_once")
            await sleep_wait(25.0, 45.0, distribution="triangular", label="error_recovery")
            continue

        if result is None:
            wait = cycle_wait_nothing_todo(policy)
            log.info("waiting %.2fs (cooldown / nothing to do)", wait)
            try:
                await asyncio.wait_for(_cancel.wait(), timeout=wait)
                break
            except asyncio.TimeoutError:
                pass
            continue

        wait = cycle_wait_after_action(policy)
        log.info("waiting %.2fs before next action", wait)
        try:
            await asyncio.wait_for(_cancel.wait(), timeout=wait)
            break
        except asyncio.TimeoutError:
            pass

    if profile.stay_in_hotel and not dry_run:
        await _book_hotel(page, profile, policy)
        log.info("session end: return to hotel")

    elapsed = datetime.now() - session_start
    log.info("session ended after %s", elapsed)


async def run_forever(page: Page, profile: BotProfile | None = None, **kwargs) -> None:
    """Entry point for webbot Python scenario integration."""
    prof = profile or __import__("mafibot.config", fromlist=["load_bot_profile"]).load_bot_profile()
    while not is_stop_requested():
        await run_session(page, prof, **kwargs)
        if is_stop_requested():
            break
        await sleep_wait(400.0, 1200.0, distribution="triangular", label="between_sessions")
