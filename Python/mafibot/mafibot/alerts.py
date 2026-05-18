"""Optional out-of-band notifications when the bot must stop."""

from __future__ import annotations

import logging
from urllib import request
from urllib.error import URLError

from mafibot.config import BotProfile

log = logging.getLogger("mafibot.alerts")


def notify_session_stop(profile: BotProfile, reason: str) -> None:
    url = (profile.stop_webhook_url or "").strip()
    if not url:
        return
    body = (
        '{"content":'
        + _json_escape(f"Mafibot [{profile.name}] stopped: {reason[:500]}")
        + "}"
    ).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                log.warning("webhook returned %s", resp.status)
    except URLError as exc:
        log.warning("stop webhook failed: %s", exc)


def _json_escape(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
