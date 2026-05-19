"""Assist-only webhooks for war/kidnap (no auto-play)."""

from __future__ import annotations

import logging

from mafibot.alerts import notify_session_stop
from mafibot.config import BotProfile
from mafibot.state import GameState

log = logging.getLogger("mafibot.assist")

_war_notified = False
_kidnap_notified = False


def reset_assist_alerts() -> None:
    global _war_notified, _kidnap_notified
    _war_notified = False
    _kidnap_notified = False


def maybe_assist_alerts(state: GameState, profile: BotProfile) -> None:
    """Post webhook when war or kidnapping is detected (once per session)."""
    global _war_notified, _kidnap_notified
    if not profile.stop_webhook_url.strip():
        return

    if profile.assist_webhook_on_war and state.family_war_active and not _war_notified:
        _war_notified = True
        log.info("assist: family war detected — webhook")
        notify_session_stop(profile, "assist: familiekrig aktiv — vurder manuell spilling")

    if profile.assist_webhook_on_kidnap and state.kidnapped and not _kidnap_notified:
        _kidnap_notified = True
        log.info("assist: kidnapped — webhook")
        notify_session_stop(profile, "assist: du er kidnappet — manuell handling kreves")
