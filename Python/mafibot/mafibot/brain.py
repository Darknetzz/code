"""Autopilot decision loop — hotel-first, slow human-paced."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from playwright.async_api import Page

from mafibot.actions.base import Action, ActionResult, action_by_name, all_actions
from mafibot.actions.hotel_book import BookHotelAction
from mafibot.actions.hotel_leave import LeaveHotelAction
from mafibot.alerts import notify_session_stop
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
    policy_after_afk_warmup,
    random_wait_seconds,
    sleep_wait,
    sleep_with_idle_activity,
    wait_with_idle_activity,
)
from mafibot.navigation import ensure_game_shell
from mafibot.assist_alerts import maybe_assist_alerts, reset_assist_alerts
from mafibot.profile_options import gameplay_paused
from mafibot.rotation import reset_rotation_state
from mafibot.scheduler import (
    action_block_reason,
    ordered_action_names,
    pick_runnable_actions,
    pick_soonest_ready,
)
from mafibot.session import capture_failure
from mafibot.session_metrics import (
    current_session_metrics,
    finish_session_metrics,
    start_session_metrics,
)
from mafibot.session_context import SessionContext
from mafibot.state import GameState, ParseError, parse_game_state

log = logging.getLogger("mafibot")

_session: SessionContext | None = None
_ROTATION_EXCLUDE = frozenset({"leave_hotel", "book_hotel", "hotel"})


def _active_session() -> SessionContext:
    global _session
    if _session is None:
        _session = SessionContext()
    return _session


@dataclass
class SessionPacing:
    actions_since_distraction: int = 0
    next_distraction_after: int = 0
    warmup_cycles_remaining: int = 0
    active_policy: HumanPolicy | None = None


def _new_session_pacing(base_policy: HumanPolicy) -> SessionPacing:
    return SessionPacing(
        next_distraction_after=random.randint(8, 15),
        active_policy=base_policy,
    )


async def _maybe_distraction_pause(
    page: Page,
    pacing: SessionPacing,
    cancel: asyncio.Event,
) -> bool:
    """Inject occasional longer idle activity between actions. Returns False if cancelled."""
    pacing.actions_since_distraction += 1
    if pacing.warmup_cycles_remaining > 0:
        pacing.warmup_cycles_remaining -= 1
        return True
    if pacing.actions_since_distraction < pacing.next_distraction_after:
        return True
    pause = random_wait_seconds(10.0, 45.0, distribution="triangular")
    log.info("distraction pause %.1fs", pause)
    policy = pacing.active_policy or HumanPolicy()
    ok = await sleep_with_idle_activity(page, pause, policy, cancel=cancel)
    pacing.actions_since_distraction = 0
    pacing.next_distraction_after = random.randint(8, 15)
    return ok


def get_last_parse_error() -> dict[str, str | None] | None:
    return _active_session().last_parse_error

StatusCallback = Callable[["GameState", str | None, str, str | None], None]
_status_callbacks: list[StatusCallback] = []


def get_last_idle_detail() -> str | None:
    return _active_session().last_idle_detail


def get_dry_run_decisions() -> list[dict[str, str | None]]:
    return [d.to_dict() for d in _active_session().dry_run_decisions]


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
            log.debug("status callback failed", exc_info=True)


def request_stop() -> None:
    _active_session().request_stop()


def clear_stop() -> None:
    global _session
    if _session is not None:
        _session.clear_stop()
    else:
        SessionContext().clear_stop()
    reset_assist_alerts()


def _effective_stay_in_hotel(profile: BotProfile) -> bool:
    return profile.stay_in_hotel and not _active_session().hotel_disabled_for_session


def _maybe_disable_hotel_for_session(profile: BotProfile) -> None:
    if not profile.hotel_fallback_when_blocked:
        return
    metrics = current_session_metrics()
    if metrics and metrics.hotel_book_failures >= 3:
        _active_session().hotel_disabled_for_session = True
        log.warning("hotel booking failed repeatedly — disabling stay_in_hotel for this session")


def is_stop_requested() -> bool:
    return _active_session().is_stop_requested()


def _record_hotel_book_outcome(result: ActionResult) -> None:
    metrics = current_session_metrics()
    if metrics is None or result.success:
        return
    msg = result.message.lower()
    if "insufficient_funds" in msg:
        metrics.record_hotel_skip("insufficient_funds")
    elif "hotel_full" in msg:
        metrics.record_hotel_skip("hotel_full")
    elif "low_wallet" in msg or "wallet" in msg:
        metrics.record_hotel_skip("wallet_low")


def _blocked_state_wait_sec(state: GameState, profile: BotProfile) -> float | None:
    """Long human-paced wait when jailed or hospitalized with nothing to do."""
    if state.in_jail:
        return random_wait_seconds(
            profile.jail_wait_min_sec,
            profile.jail_wait_max_sec,
            distribution="triangular",
        )
    if state.in_hospital:
        return random_wait_seconds(
            profile.hospital_idle_wait_min_sec,
            profile.hospital_idle_wait_max_sec,
            distribution="triangular",
        )
    return None


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


def _ordered_action_names(profile: BotProfile, state: GameState | None = None) -> list[str]:
    return ordered_action_names(profile, state)


async def _book_hotel(
    page: Page,
    profile: BotProfile,
    policy: HumanPolicy,
    *,
    dry_run: bool = False,
    quick: bool = False,
) -> ActionResult:
    if not _effective_stay_in_hotel(profile):
        return ActionResult(True, "skip book: hotel disabled for session")
    book = BookHotelAction()
    state = await parse_game_state(page)
    if not await book.can_run(state, profile):
        return ActionResult(True, "skip book: already in hotel or blocked")
    book_policy = hotel_transition_policy(policy) if quick else policy
    return await book.run(page, state, profile, book_policy, dry_run=dry_run, quick=quick)


async def _book_hotel_with_retry(
    page: Page,
    profile: BotProfile,
    policy: HumanPolicy,
    *,
    dry_run: bool = False,
    quick: bool = False,
) -> ActionResult:
    result = await _book_hotel(page, profile, policy, dry_run=dry_run, quick=quick)
    _record_hotel_book_outcome(result)
    if result.success or dry_run:
        return result
    metrics = current_session_metrics()
    if metrics:
        metrics.hotel_book_failures += 1
    log.warning("hotel book failed, retry once: %s", result.message)
    await sleep_wait(1.0, 2.5, distribution="uniform", label="hotel_book_retry")
    retry = await _book_hotel(page, profile, policy, dry_run=dry_run, quick=quick)
    _record_hotel_book_outcome(retry)
    if not retry.success:
        await capture_failure(page, "hotel_book_failed")
        if metrics:
            metrics.hotel_book_failures += 1
        _maybe_disable_hotel_for_session(profile)
    return retry


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

    if _effective_stay_in_hotel(profile) and profile.book_hotel_before_action:
        pre = await _book_hotel_with_retry(page, profile, policy, dry_run=dry_run)
        log.info("pre-action book: %s", pre.message)
        state = await parse_game_state(page)

    if _effective_stay_in_hotel(profile) and action_requires_leave_hotel(action.name):
        left = await _leave_hotel_if_needed(page, profile, policy, dry_run=dry_run)
        if left:
            log.info("leave for %s: %s", action.name, left.message)
        state = await parse_game_state(page)

    result = await action.run(page, state, profile, policy, dry_run=dry_run)

    if _effective_stay_in_hotel(profile) and profile.book_hotel_after_every_action and not dry_run:
        gap = await pause_before_book_hotel(profile.max_seconds_before_book_hotel)
        log.info("pause before book: %.2fs (max %.2fs)", gap, profile.max_seconds_before_book_hotel)
        post = await _book_hotel_with_retry(page, profile, policy, dry_run=False, quick=True)
        log.info("post-action book: %s", post.message)
        if not post.success:
            result = ActionResult(
                result.success,
                f"{result.message}; post-book failed: {post.message}",
            )

    return result


async def explain_idle(state: GameState, profile: BotProfile) -> str:
    parts: list[str] = []
    for name in _ordered_action_names(profile, state):
        action = action_by_name(name)
        if action is None:
            continue
        reason = await action_block_reason(action, state, profile)
        if reason:
            parts.append(f"{name}: {reason}")
    if not parts:
        return "nothing ready"
    return "; ".join(parts[:6])


async def pick_next_action(
    state: GameState,
    profile: BotProfile,
    *,
    dry_run: bool = False,
) -> tuple[Action | None, str]:
    ctx = _active_session()

    if state.needs_stop:
        ctx.last_idle_detail = "stop: captcha, ban, or logged out"
        return None, ctx.last_idle_detail

    if state.in_jail:
        ctx.last_idle_detail = "idle: in jail"
        return None, ctx.last_idle_detail

    maybe_assist_alerts(state, profile)

    if gameplay_paused(profile, state):
        if state.kidnapped:
            ctx.last_idle_detail = "idle: kidnapped"
        elif state.feriemodus:
            ctx.last_idle_detail = "idle: feriemodus"
        else:
            ctx.last_idle_detail = "idle: startbeskyttelse"
        return None, ctx.last_idle_detail

    names = _ordered_action_names(profile, state)
    candidates: list[Action] = []
    for name in names:
        action = action_by_name(name)
        if action is not None:
            candidates.append(action)

    if profile.scheduler == "soonest_ready":
        runnable = await pick_runnable_actions(state, profile, candidates)
        picked = pick_soonest_ready(runnable, state, names)
        if picked:
            action, reason = picked
            return action, reason
    else:
        for action in candidates:
            if await action.can_run(state, profile):
                hint = ""
                if (
                    _effective_stay_in_hotel(profile)
                    and action_requires_leave_hotel(action.name)
                    and state.in_hotel
                ):
                    hint = " (will leave hotel first)"
                return action, f"selected: {action.name}{hint}"

    allowed = set(names)
    fallback_actions = [
        a
        for a in all_actions()
        if a.name not in _ROTATION_EXCLUDE and a.name in allowed
    ]
    if profile.scheduler == "soonest_ready":
        runnable = await pick_runnable_actions(state, profile, fallback_actions)
        picked = pick_soonest_ready(runnable, state, list(allowed))
        if picked:
            return picked
    else:
        for action in fallback_actions:
            if await action.can_run(state, profile):
                return action, f"fallback: {action.name}"

    ctx.last_idle_detail = await explain_idle(state, profile)
    return None, f"nothing ready — {ctx.last_idle_detail}"


def _seconds_until_play_window(profile: BotProfile) -> float | None:
    now = datetime.now().time()
    start = time(profile.play_window.start_hour, 0)
    end = time(profile.play_window.end_hour, 0)
    if in_play_window(profile):
        return None
    if start <= end:
        if now < start:
            target = datetime.combine(datetime.now().date(), start)
        else:
            target = datetime.combine(datetime.now().date() + timedelta(days=1), start)
    else:
        if now > end and now < start:
            target = datetime.combine(datetime.now().date(), start)
        else:
            return 600.0
    return max(60.0, (target - datetime.now()).total_seconds())


async def run_once(
    page: Page,
    profile: BotProfile,
    *,
    dry_run: bool = False,
) -> ActionResult | None:
    policy = _policy_from_profile(profile)
    metrics = current_session_metrics()
    try:
        await ensure_game_shell(page, policy)
        state = await parse_game_state(page)
    except ParseError as exc:
        log.error("parse failed: %s", exc)
        shot = await capture_failure(page, "parse_error")
        if shot and not exc.screenshot_path:
            exc.screenshot_path = shot
        if metrics:
            metrics.parse_failures += 1
        detail = exc.to_dict()
        _active_session().last_parse_error = detail
        _notify_status(
            GameState(),
            None,
            f"parse error: {detail.get('detail')}",
            str(detail),
        )
        return None

    if metrics:
        metrics.record_hotel_sample(state.in_hotel)
        if metrics.money_start is None and state.money is not None:
            metrics.money_start = state.money
        if metrics.rank_start is None and state.rank_points is not None:
            metrics.rank_start = state.rank_points

    if state.needs_stop:
        reason = "captcha, ban, or logged out"
        log.warning("session stop: %s", reason)
        notify_session_stop(profile.stop_webhook_url, profile.name, reason)
        return None

    action, reason = await pick_next_action(state, profile, dry_run=dry_run)
    log.info("decision: %s", reason)
    _notify_status(state, action.name if action else None, reason, reason)

    if dry_run:
        hotel_note = ""
        if _effective_stay_in_hotel(profile):
            hotel_note = "book→action→book"
        _active_session().record_dry_run(
            action.name if action else None,
            reason,
            hotel_steps=hotel_note,
        )

    if action is None:
        if _effective_stay_in_hotel(profile) and profile.book_hotel_when_idle and not dry_run:
            await _book_hotel_with_retry(page, profile, policy)
        if metrics:
            metrics.actions_skipped += 1
        return None

    if dry_run:
        log.info("dry-run: %s (hotel wrap simulated)", action.name)
        if metrics:
            metrics.actions_run += 1
        return ActionResult(True, f"dry-run: {action.name}")

    result = await execute_with_hotel_stay(page, action, profile, policy, dry_run=False)
    log.info("action %s: success=%s msg=%s", action.name, result.success, result.message)
    if metrics:
        if result.success:
            metrics.actions_run += 1
        else:
            metrics.actions_failed += 1
    try:
        after_state = await parse_game_state(page)
    except ParseError:
        after_state = state
    _notify_status(after_state, action.name, result.message, f"done: {action.name}")
    await page_reading_pause(page)
    await between_actions(page, policy)
    return result


def _log_session_summary(profile: BotProfile, metrics) -> None:
    if metrics is None:
        return
    hotel_total = metrics.samples_in_hotel + metrics.samples_out_hotel
    pct = (
        100.0 * metrics.samples_in_hotel / hotel_total if hotel_total else 0.0
    )
    log.info(
        "session summary profile=%s actions=%s failed=%s skipped=%s parse_err=%s "
        "hotel_fail=%s in_hotel=%.0f%% money %s→%s",
        profile.name,
        metrics.actions_run,
        metrics.actions_failed,
        metrics.actions_skipped,
        metrics.parse_failures,
        metrics.hotel_book_failures,
        pct,
        metrics.money_start,
        metrics.money_end,
    )


async def run_session(
    page: Page,
    profile: BotProfile,
    *,
    max_minutes: int | None = None,
    dry_run: bool = False,
) -> None:
    global _session
    _session = SessionContext()
    reset_rotation_state()
    metrics = start_session_metrics(profile.name, dry_run=dry_run)
    policy = _policy_from_profile(profile)
    pacing = _new_session_pacing(policy)
    limit = max_minutes if max_minutes is not None else profile.max_session_minutes
    deadline = datetime.now() + timedelta(minutes=limit)
    session_start = datetime.now()
    stop_reason: str | None = None

    if _effective_stay_in_hotel(profile) and not dry_run:
        await ensure_game_shell(page, policy)
        await _book_hotel_with_retry(page, profile, policy)
        log.info("session start: ensured hotel check-in")

    cancel = _active_session().cancel
    while datetime.now() < deadline and not is_stop_requested():
        if not in_play_window(profile):
            wait_sec = _seconds_until_play_window(profile) or 600.0
            log.info("outside play window — sleeping %.0fs", wait_sec)
            if not dry_run:
                if not await sleep_with_idle_activity(
                    page, wait_sec, pacing.active_policy or policy, cancel=cancel
                ):
                    break
            else:
                try:
                    await asyncio.wait_for(cancel.wait(), timeout=wait_sec)
                    break
                except asyncio.TimeoutError:
                    pass
            continue

        if random.random() < profile.idle_chance:
            idle_sec = idle_break_seconds(profile.idle_min_minutes, profile.idle_max_minutes)
            log.info("idle break %.2f min (human AFK)", idle_sec / 60.0)
            if not dry_run:
                if not await sleep_with_idle_activity(
                    page, idle_sec, pacing.active_policy or policy, cancel=cancel
                ):
                    break
            else:
                await asyncio.sleep(idle_sec)
            pacing.active_policy = policy_after_afk_warmup(policy)
            pacing.warmup_cycles_remaining = random.randint(2, 3)
            continue

        if not dry_run and not await _maybe_distraction_pause(page, pacing, cancel):
            break

        try:
            result = await run_once(page, profile, dry_run=dry_run)
        except Exception:
            log.exception("run_once failed")
            await capture_failure(page, "run_once")
            if metrics:
                metrics.parse_failures += 1
            await sleep_wait(25.0, 45.0, distribution="triangular", label="error_recovery")
            continue

        if result is None:
            try:
                state = await parse_game_state(page)
                if state.needs_stop:
                    stop_reason = "captcha, ban, or logged out"
                    notify_session_stop(
                        profile.stop_webhook_url, profile.name, stop_reason
                    )
                    break
            except ParseError:
                state = None
            wait = cycle_wait_nothing_todo(pacing.active_policy or policy)
            if state is not None:
                blocked_wait = _blocked_state_wait_sec(state, profile)
                if blocked_wait is not None:
                    wait = blocked_wait
                    log.info(
                        "blocked state wait %.2fs (%s)",
                        wait,
                        "jail" if state.in_jail else "hospital",
                    )
            log.info("waiting %.2fs (cooldown / nothing to do)", wait)
            if dry_run:
                try:
                    await asyncio.wait_for(cancel.wait(), timeout=wait)
                    break
                except asyncio.TimeoutError:
                    pass
            elif not await wait_with_idle_activity(
                page, wait, pacing.active_policy or policy, cancel
            ):
                break
            continue

        wait = cycle_wait_after_action(pacing.active_policy or policy)
        log.info("waiting %.2fs before next action", wait)
        if dry_run:
            try:
                await asyncio.wait_for(cancel.wait(), timeout=wait)
                break
            except asyncio.TimeoutError:
                pass
        elif not await wait_with_idle_activity(
            page, wait, pacing.active_policy or policy, cancel
        ):
            break

    if is_stop_requested():
        stop_reason = stop_reason or "user stop"

    if _effective_stay_in_hotel(profile) and not dry_run:
        await _book_hotel_with_retry(page, profile, policy)
        log.info("session end: return to hotel")

    money_end: int | None = None
    rank_end: int | None = None
    try:
        final = await parse_game_state(page)
        money_end = final.money
        rank_end = final.rank_points
    except ParseError:
        pass

    finished = finish_session_metrics(
        stop_reason=stop_reason,
        money_end=money_end,
        rank_end=rank_end,
    )
    _log_session_summary(profile, finished)

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
