"""Parse game state from ms.php DOM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from playwright.async_api import Page

from mafibot.game_cities import GAME_CITIES
from mafibot.page_capture import collect_page_text, html_to_plain_text
from mafibot.selectors import (
    BAN_PATTERN,
    BUSINESS_INCOME_PATTERN,
    CAPTCHA_PATTERN,
    COOLDOWN_PATTERN,
    HEALTH_PATTERN,
    HOSPITAL_PATTERN,
    HOTEL_BLOCKS_PATTERN,
    IN_HOTEL_PATTERN,
    JAIL_PATTERN,
    KLAR_TAB_PATTERN,
    LOGGED_IN_PATTERN,
    LOGIN_HEADING,
    MONEY_PATTERN,
    POENG_PATTERN,
    RANK_PATTERN,
    SHIP_IN_PORT_PATTERN,
    TIMER_PATTERN,
    UNREAD_MESSAGES_PATTERN,
)


class ParseError(Exception):
    """Page layout unexpected or missing required signals."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "parse_failed",
        detail: str | None = None,
        screenshot_path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or message
        self.screenshot_path = screenshot_path

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": str(self),
            "detail": self.detail,
            "screenshot_path": self.screenshot_path,
        }


_HOTEL_FULL_PATTERN = re.compile(
    r"fullt\s+hotell|hotell\s+er\s+fullt|ingen\s+ledige\s+rom|ikke\s+plass",
    re.I,
)
_HOTEL_FUNDS_PATTERN = re.compile(
    r"ikke\s+nok\s+penger|for\s+lite\s+penger|mangler\s+penger",
    re.I,
)
_HOTEL_NIGHTLY_COST_PATTERN = re.compile(
    r"(?:rom|overnatt|hotell)[^.]{0,80}?([\d\s]+)\s*kr",
    re.I,
)
_WORK_READY_PATTERN = re.compile(
    r"arbeid[^.\n]{0,60}(?:klar!|kan\s+arbeide|start\s+arbeid)",
    re.I,
)
_MISSIONS_IN_PROGRESS_PATTERN = re.compile(r"på\s+oppdrag\s+\d+", re.I)


def parse_hotel_booking_hint(text: str) -> str | None:
    """Return failure reason from page text after a book attempt, or None if ok."""
    if _HOTEL_FULL_PATTERN.search(text):
        return "hotel_full"
    if _HOTEL_FUNDS_PATTERN.search(text):
        return "insufficient_funds"
    return None


def parse_hotel_nightly_cost(text: str) -> int | None:
    match = _HOTEL_NIGHTLY_COST_PATTERN.search(text)
    if not match:
        return None
    return _parse_int(match.group(1))


_BANK_BALANCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"bank(?:konto)?[:\s]+([\d\s]+)\s*kr", re.I),
    re.compile(r"på\s+konto[:\s]+([\d\s]+)\s*kr", re.I),
    re.compile(r"i\s+bank(?:en)?[:\s]+([\d\s]+)\s*kr", re.I),
    re.compile(r"saldo[:\s]+([\d\s]+)\s*kr", re.I),
)


def parse_bank_balance_from_text(text: str) -> int | None:
    for pattern in _BANK_BALANCE_PATTERNS:
        match = pattern.search(text)
        if match:
            amount = _parse_int(match.group(1))
            if amount is not None:
                return amount
    return None


@dataclass
class CooldownInfo:
    name: str
    ready_at: datetime | None = None
    raw: str = ""


@dataclass
class ActionCooldown:
    """A named game action that is currently on cooldown (not ready)."""

    id: str
    label: str
    ready_at: datetime | None = None
    raw: str = ""


# id, display label, Norwegian page keyword
_ACTION_COOLDOWN_SPECS: tuple[tuple[str, str, str], ...] = (
    ("crime", "Crime", "kriminalitet"),
    ("travel", "Travel", "flyplass"),
    ("work", "Work", "arbeid"),
    ("business", "Business", "bedrift"),
    ("ship", "Ship", "rederi"),
    ("drugs", "Drugs", "narkotika"),
    ("murder", "Murder", "skyt"),
    ("hospital", "Hospital", "sykehus"),
    ("minions", "Minions", "folk"),
    ("missions", "Missions", "oppdrag"),
    ("organized_crime", "Org crime", "organisert"),
    ("market", "Market", "marked"),
)


@dataclass
class GameState:
    logged_in: bool = False
    on_login_page: bool = False
    in_game_shell: bool = False
    player_name: str | None = None
    money: int | None = None
    bank_balance: int | None = None
    rank_points: int | None = None
    health_percent: int | None = None
    location: str | None = None
    current_side: str | None = None
    active_tab: str | None = None
    unread_messages: int = 0
    in_jail: bool = False
    in_hospital: bool = False
    in_hotel: bool = False
    hotel_blocks_actions: bool = False
    captcha: bool = False
    banned: bool = False
    business_income_ready: bool = False
    ship_in_port: bool = False
    hotel_nightly_cost: int | None = None
    missions_in_progress: bool = False
    crime_ready: bool = True
    travel_ready: bool = True
    work_ready: bool = True
    job_ready: bool = True
    hotel_ready: bool = True
    ship_ready: bool = True
    drugs_ready: bool = True
    murder_ready: bool = True
    hospital_ready: bool = True
    minions_ready: bool = True
    missions_ready: bool = True
    organized_crime_ready: bool = True
    market_ready: bool = True
    cooldowns: list[CooldownInfo] = field(default_factory=list)
    active_cooldowns: list[ActionCooldown] = field(default_factory=list)
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

    def low_health_for_profile(self, min_health_percent: int) -> bool:
        if self.health_percent is None:
            return False
        return self.health_percent < min_health_percent

    @property
    def must_leave_hotel(self) -> bool:
        return self.in_hotel and self.hotel_blocks_actions


def _parse_int(s: str | None) -> int | None:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def _timer_to_seconds(h: int, m: int, s: int = 0) -> int:
    return h * 3600 + m * 60 + s


def _cooldown_block(text: str, keyword: str) -> str:
    lines = [ln for ln in text.splitlines() if keyword.lower() in ln.lower()]
    if not lines:
        return ""
    return "\n".join(lines)


def _duration_from_cooldown_match(raw: str, amount: int) -> int:
    lower = raw.lower()
    if re.search(r"\bsek(?:und)?", lower):
        return amount
    if re.search(r"\btimer?\b|\bt\b", lower):
        return amount * 3600
    return amount * 60


def _estimate_ready_at(text: str) -> tuple[datetime | None, str]:
    m = TIMER_PATTERN.search(text)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        return datetime.now() + timedelta(seconds=_timer_to_seconds(h, mi, s)), m.group(0)
    m = COOLDOWN_PATTERN.search(text)
    if m:
        raw = m.group(0)
        amount = int(m.group(1))
        return datetime.now() + timedelta(seconds=_duration_from_cooldown_match(raw, amount)), raw
    return None, ""


def _cooldown_ready(text: str, keyword: str) -> bool:
    block = _cooldown_block(text, keyword)
    if not block:
        return True
    if re.search(r"klar!|kan\s+hentes|står\s+i\s+havn", block, re.I):
        return True
    if COOLDOWN_PATTERN.search(block):
        return False
    if TIMER_PATTERN.search(block):
        return False
    if re.search(r"må\s+vente|vente\s+\d|ikke\s+mulig|for\s+tidlig|på\s+oppdrag", block, re.I):
        return False
    # Heading-only line (e.g. "Kriminalitet") — look at full page for wait messages
    lines = [ln for ln in text.splitlines() if keyword.lower() in ln.lower()]
    if len(lines) == 1 and len(lines[0].strip()) < 24:
        if re.search(rf"må\s+vente[^.\n]*{re.escape(keyword)}", text, re.I):
            return False
        if re.search(r"vente\s+\d+[^.\n]*(?:min|minutt)", text, re.I) and keyword.lower() in text.lower():
            return False
    return True


def _action_is_on_cooldown(state: GameState, action_id: str) -> bool:
    return {
        "crime": not state.crime_ready,
        "travel": not state.travel_ready,
        "work": not state.job_ready,
        "business": not state.work_ready,
        "ship": not state.ship_ready,
        "drugs": not state.drugs_ready,
        "murder": not state.murder_ready,
        "hospital": not state.hospital_ready,
        "minions": not state.minions_ready,
        "missions": not state.missions_ready,
        "organized_crime": not state.organized_crime_ready,
        "market": not state.market_ready,
    }.get(action_id, False)


def collect_active_cooldowns(state: GameState, text: str) -> list[ActionCooldown]:
    """Return only actions that are not ready (on cooldown)."""
    active: list[ActionCooldown] = []
    for action_id, label, keyword in _ACTION_COOLDOWN_SPECS:
        if not _action_is_on_cooldown(state, action_id):
            continue
        block = _cooldown_block(text, keyword)
        hint = block or text
        ready_at, raw = _estimate_ready_at(hint)
        if action_id == "crime" and state.in_jail:
            label = "Crime (jail)"
        active.append(
            ActionCooldown(id=action_id, label=label, ready_at=ready_at, raw=raw)
        )
    return active


def _detect_location(text: str) -> str | None:
    for name in (*GAME_CITIES, "Beirut"):
        if re.search(rf"\b{name}\b", text):
            return name
    return None


async def parse_game_state(page: Page) -> GameState:
    url = page.url
    side = None
    if "side=" in url:
        side = url.split("side=", 1)[-1].split("&", 1)[0]

    try:
        body_text = await collect_page_text(page)
    except Exception as exc:
        raise ParseError(
            f"Could not read page body: {exc}",
            code="body_read_failed",
            detail=str(exc),
        ) from exc

    text = body_text[:16000]
    state = GameState(
        current_side=side,
        in_game_shell="ms.php" in url.lower(),
        page_text_sample=text[:500],
        parsed_at=datetime.now(),
    )

    state.on_login_page = bool(LOGIN_HEADING.search(text)) and "passord" in text.lower()
    state.logged_in = bool(LOGGED_IN_PATTERN.search(text)) or (
        state.in_game_shell and not state.on_login_page
    )
    state.captcha = bool(CAPTCHA_PATTERN.search(text))
    state.in_jail = bool(JAIL_PATTERN.search(text))
    state.in_hospital = bool(HOSPITAL_PATTERN.search(text))
    state.banned = bool(BAN_PATTERN.search(text))
    state.in_hotel = bool(IN_HOTEL_PATTERN.search(text))
    state.hotel_blocks_actions = bool(HOTEL_BLOCKS_PATTERN.search(text))
    state.business_income_ready = bool(BUSINESS_INCOME_PATTERN.search(text))
    state.ship_in_port = bool(SHIP_IN_PORT_PATTERN.search(text))
    state.hotel_nightly_cost = parse_hotel_nightly_cost(text)
    state.missions_in_progress = bool(_MISSIONS_IN_PROGRESS_PATTERN.search(text))

    money_m = MONEY_PATTERN.search(text)
    if money_m:
        state.money = _parse_int(money_m.group(1))
    state.bank_balance = parse_bank_balance_from_text(text)
    poeng_m = POENG_PATTERN.search(text)
    if poeng_m:
        state.rank_points = int(poeng_m.group(1))
    health_m = HEALTH_PATTERN.search(text)
    if health_m:
        state.health_percent = _parse_int(health_m.group(1))
    state.location = _detect_location(text)

    if "Kriminalitet" in text and "Klar!" in text:
        state.active_tab = "Kriminalitet"
    elif "Flyplass" in text:
        state.active_tab = "Flyplass"

    unread_m = UNREAD_MESSAGES_PATTERN.search(text)
    if unread_m:
        state.unread_messages = int(unread_m.group(1))

    state.crime_ready = _cooldown_ready(text, "kriminalitet") and not state.in_jail
    state.travel_ready = _cooldown_ready(text, "flyplass") or bool(KLAR_TAB_PATTERN.search(text))
    state.job_ready = _cooldown_ready(text, "arbeid") or bool(_WORK_READY_PATTERN.search(text))
    state.work_ready = state.business_income_ready or _cooldown_ready(text, "bedrift")
    state.ship_ready = state.ship_in_port or _cooldown_ready(text, "rederi")
    state.drugs_ready = _cooldown_ready(text, "narkotika")
    state.murder_ready = _cooldown_ready(text, "skyt")
    state.hospital_ready = _cooldown_ready(text, "sykehus")
    state.minions_ready = _cooldown_ready(text, "folk") or _cooldown_ready(text, "undersåtter")
    state.missions_ready = (
        not state.missions_in_progress
        and (_cooldown_ready(text, "oppdrag") or _cooldown_ready(text, "oppdrag2"))
    )
    state.organized_crime_ready = _cooldown_ready(text, "organisert")
    state.market_ready = _cooldown_ready(text, "marked")

    for m in COOLDOWN_PATTERN.finditer(text):
        state.cooldowns.append(CooldownInfo(name="generic", raw=m.group(0)))
    for m in TIMER_PATTERN.finditer(text):
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        ready = datetime.now() + timedelta(seconds=_timer_to_seconds(h, mi, s))
        state.cooldowns.append(CooldownInfo(name="timer", ready_at=ready, raw=m.group(0)))

    state.active_cooldowns = collect_active_cooldowns(state, text)

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
            return html_to_plain_text(self._html)

    return await parse_game_state(_FakePage())  # type: ignore[arg-type]
