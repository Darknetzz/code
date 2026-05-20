"""Optional out-of-band notifications (Discord-compatible webhooks)."""

from __future__ import annotations

import json
import logging
import time
from urllib import request
from urllib.error import URLError

log = logging.getLogger("mafibot.alerts")


def post_webhook(
    url: str,
    message: str,
    *,
    retries: int = 2,
    timeout: float = 10.0,
) -> bool:
    """POST JSON {content: message} to a webhook URL."""
    url = (url or "").strip()
    if not url:
        return False
    body = json.dumps({"content": message[:1900]}).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                if resp.status >= 400:
                    log.warning("webhook returned %s", resp.status)
                    return False
                return True
        except URLError as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    log.warning("webhook failed: %s", last_exc)
    return False


def notify_webhook(url: str, message: str) -> None:
    post_webhook(url, message)


def notify_session_stop(stop_url: str, profile_name: str, reason: str) -> None:
    url = (stop_url or "").strip()
    if not url:
        return
    notify_webhook(url, f"Mafibot [{profile_name}] stopped: {reason[:500]}")


def notify_assist(assist_url: str, profile_name: str, reason: str) -> None:
    url = (assist_url or "").strip()
    if not url:
        return
    notify_webhook(url, f"Mafibot [{profile_name}] assist: {reason[:500]}")
