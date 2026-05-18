"""Autopilot decision loop — slow, human-paced."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta

from playwright.async_api import Page

from mafibot.actions.base import Action, ActionResult, action_by_name, all_actions
from mafibot.config import BotProfile, in_play_window
from mafibot.human_policy import HumanPolicy, between_actions, cooldown_jitter, page_reading_pause
from mafibot.navigation import ensure_game_shell
from mafibot.session import capture_failure
from mafibot.state import GameState, ParseError, parse_game_state

log = logging.getLogger("mafibot")

_cancel = asyncio.Event()


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
    )


def _ordered_action_names(profile: BotProfile) -> list[str]:
    order: list[str] = []
    if "leave_hotel" not in profile.economy_order:
        order.append("leave_hotel")
    for name in profile.economy_order:
        if name not in order:
            order.append(name)
    if profile.social_enabled:
        for s in ("messages", "family"):
            if s not in order:
                order.append(s)
    if profile.combat_enabled and "murder" not in order:
        order.append("murder")
    # Map legacy "work" to business on ms.php
    normalized = []
    for n in order:
        if n == "work":
            normalized.append("business")
        elif n not in normalized:
            normalized.append(n)
    return normalized


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

    leave = action_by_name("leave_hotel")
    if leave and await leave.can_run(state, profile):
        return leave, "priority: leave hotel before other actions"

    if state.in_hospital or (state.low_health and profile.min_health_percent):
        hotel = action_by_name("hotel")
        if hotel and await hotel.can_run(state, profile):
            return hotel, "safety: low health -> hotel"

    for name in _ordered_action_names(profile):
        action = action_by_name(name)
        if action is None:
            continue
        if await action.can_run(state, profile):
            return action, f"selected: {name}"

    for action in all_actions():
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
        log.warning("session stop: captcha=%s banned=%s login=%s", state.captcha, state.banned, state.on_login_page)
        return None

    action, reason = await pick_next_action(state, profile, dry_run=dry_run)
    log.info("decision: %s", reason)
    if action is None:
        return None

    if dry_run:
        log.info("dry-run: %s", action.name)
        return ActionResult(True, f"dry-run: {action.name}")

    result = await action.run(page, state, profile, policy, dry_run=False)
    log.info("action %s: success=%s msg=%s", action.name, result.success, result.message)
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

    while datetime.now() < deadline and not is_stop_requested():
        if not in_play_window(profile):
            log.info("outside play window — sleeping 10 min")
            await asyncio.sleep(600)
            continue

        if random.random() < profile.idle_chance:
            idle_min = random.randint(profile.idle_min_minutes, profile.idle_max_minutes)
            log.info("idle break %s min (human AFK)", idle_min)
            await asyncio.sleep(idle_min * 60)
            continue

        try:
            result = await run_once(page, profile, dry_run=dry_run)
        except Exception:
            log.exception("run_once failed")
            await capture_failure(page, "run_once")
            await asyncio.sleep(random.uniform(25, 45))
            continue

        if result is None:
            wait = cooldown_jitter(policy) + random.uniform(45, 180)
            log.info("waiting %.0fs (cooldown / nothing to do)", wait)
            try:
                await asyncio.wait_for(_cancel.wait(), timeout=wait)
                break
            except asyncio.TimeoutError:
                pass
            continue

        wait = cooldown_jitter(policy) + random.uniform(8, 25)
        try:
            await asyncio.wait_for(_cancel.wait(), timeout=wait)
            break
        except asyncio.TimeoutError:
            pass

    elapsed = datetime.now() - session_start
    log.info("session ended after %s", elapsed)


async def run_forever(page: Page, profile: BotProfile | None = None, **kwargs) -> None:
    """Entry point for webbot Python scenario integration."""
    prof = profile or __import__("mafibot.config", fromlist=["load_bot_profile"]).load_bot_profile()
    while not is_stop_requested():
        await run_session(page, prof, **kwargs)
        if is_stop_requested():
            break
        await asyncio.sleep(random.uniform(400, 1200))
