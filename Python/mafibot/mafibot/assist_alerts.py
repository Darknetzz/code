"""Assist-only webhooks for war/kidnap (no auto-play)."""

from __future__ import annotations

import logging

from mafibot.alerts import notify_assist
from mafibot.config import BotProfile
from mafibot.state import GameState

log = logging.getLogger("mafibot.assist")

_war_notified = False
_kidnap_notified = False


def reset_assist_alerts() -> None:
    global _war_notified, _kidnap_notified
    _war_notified = False
    _kidnap_notified = False


def _assist_webhook_url(profile: BotProfile) -> str:
    return (profile.assist_webhook_url or profile.stop_webhook_url or "").strip()


def maybe_assist_alerts(state: GameState, profile: BotProfile) -> None:
    """Post webhook when war or kidnapping is detected (once per session)."""
    global _war_notified, _kidnap_notified
    url = _assist_webhook_url(profile)
    if not url:
        return

    if profile.assist_webhook_on_war and state.family_war_active and not _war_notified:
        _war_notified = True
        log.info("assist: family war detected — webhook")
        notify_assist(
            url,
            profile.name,
            "familiekrig aktiv — vurder manuell spilling",
        )

    if profile.assist_webhook_on_kidnap and state.kidnapped and not _kidnap_notified:
        _kidnap_notified = True
        log.info("assist: kidnapped — webhook")
        notify_assist(
            url,
            profile.name,
            "du er kidnappet — manuell handling kreves",
        )
