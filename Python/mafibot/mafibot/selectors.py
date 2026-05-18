"""Norwegian UI labels and page keys — refine via `mafibot.py discover`."""

from __future__ import annotations

import json
import re
from pathlib import Path

from mafibot.config import get_pages_config_path

# Logical action -> default ?side= slug (overridden by discovery pages.json)
DEFAULT_SIDES: dict[str, str] = {
    "home": "forsiden",
    "crime": "kriminalitet",
    "crime_light": "kriminalitet",
    "crime_heavy": "kriminalitet",
    "theft": "tyveri",
    "travel": "reise",
    "hotel": "hotell",
    "work": "arbeid",
    "bank": "bank",
    "ship": "rederi",
    "drugs": "narkotika",
    "messages": "meldinger",
    "family": "familie",
    "murder": "drap",
    "status": "status",
}

# Link text patterns (case-insensitive substring)
NAV_LINKS: dict[str, tuple[str, ...]] = {
    "crime": ("kriminalitet", "krim"),
    "travel": ("reise", "fly"),
    "hotel": ("hotell",),
    "work": ("arbeid",),
    "bank": ("bank",),
    "ship": ("rederi", "skip"),
    "drugs": ("narkotika", "narko"),
    "messages": ("meldinger", "melding"),
    "family": ("familie", "gjeng"),
    "murder": ("drap",),
    "logout": ("logg ut", "log out"),
    "login": ("logg inn",),
}

LOGIN_HEADING = re.compile(r"logg\s+inn", re.I)
LOGOUT_PATTERN = re.compile(r"logg\s+ut", re.I)
CAPTCHA_PATTERN = re.compile(r"captcha|robot|bekreft\s+at\s+du", re.I)
JAIL_PATTERN = re.compile(r"fengsel|sitter\s+i\s+fengsel", re.I)
HOSPITAL_PATTERN = re.compile(r"sykehus|hospitalisert", re.I)
BAN_PATTERN = re.compile(r"utestengt|bannet|ikke\s+tilgang", re.I)

MONEY_PATTERN = re.compile(
    r"(?:penger|kontanter|saldo|bank)[:\s]*([\d\s\.]+)",
    re.I,
)
RANK_PATTERN = re.compile(r"(?:rank|rankpoeng)[:\s]*([\d\s\.]+)", re.I)
HEALTH_PATTERN = re.compile(r"(?:liv|helse|health)[:\s]*(\d+)\s*%?", re.I)
LOCATION_PATTERN = re.compile(
    r"(?:du\s+er\s+i|lokasjon|by)[:\s]*([A-Za-zæøåÆØÅ\s\-]+)",
    re.I,
)
COOLDOWN_PATTERN = re.compile(
    r"(?:vent|cooldown|kan\s+ikke)[^.]*?(\d+)\s*(?:min|minutt|sek|timer|t)",
    re.I,
)
TIMER_PATTERN = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
UNREAD_MESSAGES_PATTERN = re.compile(r"(\d+)\s*(?:uleste|nye)\s*melding", re.I)

# Submit / action button labels
CRIME_ACTION_LABELS = ("begå", "utfør", "start", "gjør")
TRAVEL_ACTION_LABELS = ("reise", "fly", "reise til")
WORK_ACTION_LABELS = ("arbeid", "jobb")
HOTEL_ACTION_LABELS = ("book", "sjekk inn", "hotell")
SHIP_ACTION_LABELS = ("send", "skip", "avreise")
DRUGS_ACTION_LABELS = ("kjøp", "selg", "narkotika")
MURDER_ACTION_LABELS = ("drap", "skyt", "angrip")
MESSAGE_REPLY_LABELS = ("svar", "send")


def load_pages_map() -> dict[str, str]:
    path = get_pages_config_path()
    if not path.is_file():
        return dict(DEFAULT_SIDES)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sides = data.get("sides", data)
        if isinstance(sides, dict):
            merged = dict(DEFAULT_SIDES)
            merged.update({str(k): str(v) for k, v in sides.items()})
            return merged
    except (json.JSONDecodeError, OSError):
        pass
    return dict(DEFAULT_SIDES)


def side_for(logical: str) -> str:
    return load_pages_map().get(logical, DEFAULT_SIDES.get(logical, logical))


def save_pages_map(sides: dict[str, str], discovered_links: list[dict] | None = None) -> Path:
    path = get_pages_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"sides": sides}
    if discovered_links is not None:
        payload["discovered_links"] = discovered_links
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
