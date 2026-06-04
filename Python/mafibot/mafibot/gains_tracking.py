"""Record per-action gains into session metrics and session log."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.action_outcome import parse_action_outcome
from mafibot.gains_ledger import source_for_action
from mafibot.minions_page import MinionsRoster, roster_skill_totals
from mafibot.page_capture import collect_page_text
from mafibot.session_log import log_session_event
from mafibot.session_metrics import SessionMetrics
from mafibot.state import GameState


def _money_delta(before: int | None, after: int | None) -> int:
    if before is None or after is None:
        return 0
    return after - before


def _rank_delta(before: int | None, after: int | None) -> int:
    if before is None or after is None:
        return 0
    return after - before


async def record_action_gains(
    metrics: SessionMetrics,
    *,
    page: Page,
    action_name: str,
    result_source: str | None,
    success: bool,
    message: str,
    before_state: GameState,
    after_state: GameState,
    minions_before: MinionsRoster | None = None,
    minions_after: MinionsRoster | None = None,
) -> None:
    if metrics.dry_run:
        return

    source = source_for_action(action_name, result_source=result_source)
    money_delta = _money_delta(before_state.money, after_state.money)
    rank_delta = _rank_delta(before_state.rank_points, after_state.rank_points)

    try:
        page_text = await collect_page_text(page)
    except Exception:
        page_text = ""
    hints = parse_action_outcome(page_text, action=action_name, source=source)

    if money_delta == 0 and hints.money_delta:
        money_delta = hints.money_delta
    if rank_delta == 0 and hints.rank_delta:
        rank_delta = hints.rank_delta

    ledger = metrics.gains
    ledger.record_action_event(
        action=action_name,
        source=source,
        success=success,
        money_delta=money_delta,
        rank_delta=rank_delta,
        message=message,
    )
    if hints.cannabis_grams or hints.opium_grams:
        ledger.record_grams_sold(
            cannabis=hints.cannabis_grams,
            opium=hints.opium_grams,
        )

    if minions_before is not None and minions_after is not None:
        before_skills = roster_skill_totals(minions_before)
        after_skills = roster_skill_totals(minions_after)
        for skill in ("angrep", "beskyttelse", "intelligens"):
            delta = round(after_skills.get(skill, 0.0) - before_skills.get(skill, 0.0), 1)
            ledger.record_minion_skill(skill, delta)

    log_session_event(
        "ACTION",
        action=action_name,
        source=source,
        ok=success,
        money_delta=money_delta,
        rank_delta=rank_delta,
        cannabis=hints.cannabis_grams or None,
        opium=hints.opium_grams or None,
        msg=message[:120] if message else None,
    )


def log_session_gains_summary(metrics: SessionMetrics) -> None:
    g = metrics.gains
    log_session_event(
        "SUMMARY",
        money_net=g.money_net,
        rank_net=g.rank_points_net,
        cannabis=g.cannabis_grams_sold,
        opium=g.opium_grams_sold,
        minion_skills=g.minion_skills_net or None,
    )
