"""Parse game state from the current page DOM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from playwright.async_api import Page

from mafibot.selectors import (
    BAN_PATTERN,
    CAPTCHA_PATTERN,
    COOLDOWN_PATTERN,
    HEALTH_PATTERN,
    HOSPITAL_PATTERN,
    JAIL_PATTERN,
    LOCATION_PATTERN,
    LOGIN_HEADING,
    LOGOUT_PATTERN,
    MONEY_PATTERN,
    RANK_PATTERN,
    TIMER_PATTERN,
    UNREAD_MESSAGES_PATTERN,
)


class ParseError(Exception):
    """Page layout unexpected or missing required signals."""


@dataclass
class CooldownInfo:
    name: str
    ready_at: datetime | None = None
    raw: str = ""


@dataclass
class GameState:
    logged_in: bool = False
    on_login_page: bool = False
    player_name: str | None = None
    money: int | None = None
    rank_points: int | None = None
    health_percent: int | None = None
    location: str | None = None
    current_side: str | None = None
    unread_messages: int = 0
    in_jail: bool = False
    in_hospital: bool = False
    captcha: bool = False
    banned: bool = False
    crime_ready: bool = True
    travel_ready: bool = True
    work_ready: bool = True
    hotel_ready: bool = True
    ship_ready: bool = True
    drugs_ready: bool = True
    murder_ready: bool = True
    cooldowns: list[CooldownInfo] = field(default_factory=list)
    page_text_sample: str = ""
    parsed_at: datetime = field(default_factory=datetime.now)

    @property
    def needs_stop(self) -> bool:
        return self.captcha or self.banned or self.on_login_page

    @property
    def low_health(self) -> bool:
        if self.health_percent is None:
            return False
        return self.health_percent < 35


def _parse_int(s: str | None) -> int | None:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def _timer_to_seconds(h: int, m: int, s: int = 0) -> int:
    return h * 3600 + m * 60 + s


def _cooldown_ready(text: str, keyword: str) -> bool:
    block = _extract_block(text, keyword)
    if not block:
        return True
    if re.search(r"kan\s+(?:nå|godt)", block, re.I):
        return True
    if COOLDOWN_PATTERN.search(block):
        return False
    if TIMER_PATTERN.search(block):
        return False
    if re.search(r"vente|ikke\s+mulig|for\s+tidlig", block, re.I):
        return False
    return True


def _extract_block(text: str, keyword: str) -> str:
    for line in text.splitlines():
        if keyword.lower() in line.lower():
            return line
    return ""


async def parse_game_state(page: Page) -> GameState:
    url = page.url
    side = None
    if "side=" in url:
        side = url.split("side=", 1)[-1].split("&", 1)[0]

    try:
        body_text = await page.locator("body").inner_text()
    except Exception as exc:
        raise ParseError(f"Could not read page body: {exc}") from exc

    text = body_text[:12000]
    state = GameState(current_side=side, page_text_sample=text[:500], parsed_at=datetime.now())

    state.on_login_page = bool(LOGIN_HEADING.search(text)) and "passord" in text.lower()
    state.logged_in = bool(LOGOUT_PATTERN.search(text)) or (
        not state.on_login_page and "logg inn" not in text.lower()[:800]
    )
    state.captcha = bool(CAPTCHA_PATTERN.search(text))
    state.in_jail = bool(JAIL_PATTERN.search(text))
    state.in_hospital = bool(HOSPITAL_PATTERN.search(text))
    state.banned = bool(BAN_PATTERN.search(text))

    money_m = MONEY_PATTERN.search(text)
    if money_m:
        state.money = _parse_int(money_m.group(1))
    rank_m = RANK_PATTERN.search(text)
    if rank_m:
        state.rank_points = _parse_int(rank_m.group(1))
    health_m = HEALTH_PATTERN.search(text)
    if health_m:
        state.health_percent = _parse_int(health_m.group(1))
    loc_m = LOCATION_PATTERN.search(text)
    if loc_m:
        state.location = loc_m.group(1).strip()[:80]

    unread_m = UNREAD_MESSAGES_PATTERN.search(text)
    if unread_m:
        state.unread_messages = int(unread_m.group(1))

    state.crime_ready = _cooldown_ready(text, "kriminalitet") or _cooldown_ready(text, "krim")
    state.travel_ready = _cooldown_ready(text, "reise")
    state.work_ready = _cooldown_ready(text, "arbeid")
    state.hotel_ready = _cooldown_ready(text, "hotell")
    state.ship_ready = _cooldown_ready(text, "rederi") or _cooldown_ready(text, "skip")
    state.drugs_ready = _cooldown_ready(text, "narkotika")
    state.murder_ready = _cooldown_ready(text, "drap")

    for m in COOLDOWN_PATTERN.finditer(text):
        state.cooldowns.append(CooldownInfo(name="generic", raw=m.group(0)))
    for m in TIMER_PATTERN.finditer(text):
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        ready = datetime.now() + timedelta(seconds=_timer_to_seconds(h, mi, s))
        state.cooldowns.append(CooldownInfo(name="timer", ready_at=ready, raw=m.group(0)))

    if state.on_login_page:
        state.logged_in = False

    return state


async def parse_from_html(html: str, page_url: str = "") -> GameState:
    """Parse state from saved HTML (tests / fixtures)."""

    class _FakePage:
        def __init__(self) -> None:
            self.url = page_url
            self._html = html

        def locator(self, _sel: str):
            return self

        async def inner_text(self) -> str:
            body = re.search(r"<body[^>]*>(.*)</body>", self._html, re.I | re.S)
            raw = body.group(1) if body else self._html
            raw = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<[^>]+>", " ", raw)
            return re.sub(r"\s+", " ", raw).strip()

    return await parse_game_state(_FakePage())  # type: ignore[arg-type]
