"""Norwegian UI labels — ms.php tab UI (2026) + legacy ?side= fallback."""

from __future__ import annotations

import json
import re
from pathlib import Path

from mafibot.config import get_pages_config_path

# Logged-in game shell uses ms.php and top tabs (primary navigation).
GAME_TABS: dict[str, str] = {
    "home": "Hjem",
    "crime": "Kriminalitet",
    "minions": "Undersåtter",
    "missions": "Oppdrag",
    "travel": "Flyplass",
    "organized_crime": "Organisert Kriminalitet",
    "forum": "Forum",
    "market": "Marked",
    "hospital": "Sykehus",
    "family": "Familie",
    "business": "Store bedrifter",
    "hotel": "Hotell",
    "messages": "Meldinger",
}

# Sidebar / in-page links (partial match)
SIDEBAR_LINKS: dict[str, tuple[str, ...]] = {
    "business": ("mine bedrifter",),
    "ship": ("mitt rederi",),
    "drugs": ("narkotika",),
    "murder": ("skyt",),
    "bank": ("bank",),
}

# Legacy ?side= slugs (fallback if redirected off ms.php)
DEFAULT_SIDES: dict[str, str] = {
    "home": "forsiden",
    "crime": "kriminalitet",
    "minions": "folk",
    "missions": "oppdrag",
    "travel": "reise",
    "organized_crime": "org_krim",
    "market": "marked",
    "hotel": "hotell",
    "bank": "bank",
    "ship": "rederi",
    "drugs": "narkotika",
    "messages": "meldinger",
    "family": "familie",
    "murder": "drap",
    "hospital": "sykehus",
}

# game.php?p= route → logical page (from ms.php tab data-url)
TAB_FRAME_ROUTES: dict[str, str] = {
    "hjem": "home",
    "krim": "crime",
    "folk": "minions",
    "oppdrag2": "missions",
    "oppdrag": "missions",
    "flyplass2": "travel",
    "flyplass": "travel",
    "org_krim": "organized_crime",
    "org_kriminalitet": "organized_crime",
    "marked": "market",
    "forum": "forum",
    "sykehus": "hospital",
    "familie": "family",
    "hotell": "hotel",
    "meldinger": "messages",
    "bedrifter": "business",
}

NAV_LINKS: dict[str, tuple[str, ...]] = {
    "crime": ("kriminalitet",),
    "minions": ("undersåtter", "folk"),
    "missions": ("oppdrag",),
    "organized_crime": ("organisert",),
    "market": ("marked",),
    "travel": ("flyplass", "reise"),
    "hotel": ("hotell",),
    "bank": ("bank",),
    "ship": ("rederi", "skip", "mitt rederi"),
    "drugs": ("narkotika",),
    "messages": ("meldinger",),
    "family": ("familie",),
    "murder": ("drap", "skyt"),
    "business": ("bedrifter", "mine bedrifter"),
    "hospital": ("sykehus",),
}

# Detection (ms.php body text)
LOGIN_HEADING = re.compile(r"logg\s+inn", re.I)
GAME_SHELL_PATTERN = re.compile(r"ms\.php", re.I)
LOGGED_IN_PATTERN = re.compile(r"Penger:\s*[\d\s]+", re.I)
PLAYER_NAME_PATTERN = re.compile(
    r'class="header-item-username"[\s\S]{0,800}?<span>([^<]+)</span>',
    re.I,
)
POENG_PATTERN = re.compile(r"Poeng:\s*(\d+)", re.I)
MONEY_PATTERN = re.compile(r"Penger:\s*([\d\s]+)\s*kr", re.I)
RANK_PATTERN = re.compile(r"Rank:\s*([^\n]+)", re.I)
HEALTH_PATTERN = re.compile(r"Helse:\s*(\d+)\s*%", re.I)
LOCATION_HEADER_PATTERN = re.compile(r"^([A-ZÆØÅ][A-Za-zæøåÆØÅ]+)\s*$", re.M)

IN_HOTEL_PATTERN = re.compile(r"sjekk\s+ut\s*\(|forlat\s+hotell|i\s+hotell", re.I)
HOTEL_BLOCKS_PATTERN = re.compile(r"forlat\s+hotell\s+for\s+å\s+utføre", re.I)
KLAR_TAB_PATTERN = re.compile(r"Klar!", re.I)
BUSINESS_INCOME_PATTERN = re.compile(r"inntekt\s+kan\s+hentes", re.I)
SHIP_IN_PORT_PATTERN = re.compile(r"skip\s+står\s+i\s+havn", re.I)

CAPTCHA_PATTERN = re.compile(r"captcha|robot|bekreft\s+at\s+du", re.I)
JAIL_PATTERN = re.compile(r"fengsel|sitter\s+i\s+fengsel", re.I)
HOSPITAL_PATTERN = re.compile(r"sykehus|hospitalisert", re.I)
BAN_PATTERN = re.compile(r"utestengt|bannet|ikke\s+tilgang", re.I)
COOLDOWN_PATTERN = re.compile(
    r"(?:vent|kan\s+ikke)[^.]*?(\d+)\s*(?:min|minutt|sek|timer|t)",
    re.I,
)
TIMER_PATTERN = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
UNREAD_MESSAGES_PATTERN = re.compile(r"(\d+)\s*(?:uleste|nye)\s*melding", re.I)

# Buttons (ms.php)
CRIME_ACTION_LABELS = ("utfør", "stjel", "begå", "gjør")
TRAVEL_ACTION_LABELS = ("reise", "fly", "avgang")
BUSINESS_ACTION_LABELS = ("hent", "inntekt", "samle inntekt")
MINIONS_ACTION_LABELS = ("utfør", "samle", "bruk", "folk")
MINIONS_TRAIN_LABELS = (
    "trene",
    "tren",
    "trening",
    "tren undersåtter",
    "tren alle",
    "tren alle!",
)
MISSIONS_ACTION_LABELS = ("start", "oppdrag", "utfør", "dra på oppdrag")
ORG_CRIME_ACTION_LABELS = ("utfør", "begå", "deltak", "start")


def market_item_labels(item_id: str) -> tuple[str, ...]:
    item_id = item_id.lower().strip()
    if item_id in ("våpen", "vapen", "weapon"):
        return ("våpen", "skytevåpen", "pistol")
    if item_id in ("kuler", "bullets", "ammo"):
        return ("kuler", "ammunisjon", "patroner")
    if item_id in ("bil", "car"):
        return ("bil", "kjøretøy", "bilkjøp")
    return (item_id,)


def org_crime_difficulty_labels(level: str) -> tuple[str, ...]:
    level = level.lower()
    if level == "lett":
        return ("lett", "enkel", "lav")
    if level == "hard":
        return ("hard", "vanskelig", "tung")
    return ("medium", "middels", "normal")
MARKET_ACTION_LABELS = ("kjøp", "selg", "marked", "by")
HOTEL_LEAVE_LABELS = ("forlat hotell", "sjekk ut")
HOTEL_BOOK_LABELS = ("book hotell", "sjekk inn", "overnatt")
SHIP_ACTION_LABELS = ("send", "avreise", "skip")
DRUGS_ACTION_LABELS = ("kjøp", "selg", "narkotika")
MURDER_ACTION_LABELS = ("skyt", "drap", "angrip")
STEAL_RANDOM_TARGET_LABELS = (
    "tilfeldig",
    "random",
    "trekk",
    "velg tilfeldig",
    "tilfeldig spiller",
    "tilfeldig bruker",
)

HOSPITAL_ACTION_LABELS = (
    "behandle",
    "helbred",
    "full helse",
    "kur",
    "sykehus",
    "innleggelse",
    "hent helse",
)
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


# Dashboard / live-status labels (keep in sync with mafibot/static/app.js ACTION_CATALOG)
ACTION_DISPLAY_LABELS: dict[str, str] = {
    "hospital": GAME_TABS["hospital"],
    "crime": GAME_TABS["crime"],
    "business": "Mine bedrifter",
    "ship": "Mitt rederi",
    "travel": GAME_TABS["travel"],
    "drugs": "Narkotika",
    "bank": "Bank",
    "messages": GAME_TABS["messages"],
    "family": GAME_TABS["family"],
    "minions": GAME_TABS["minions"],
    "missions": GAME_TABS["missions"],
    "organized_crime": GAME_TABS["organized_crime"],
    "market": GAME_TABS["market"],
    "murder": "Skyt",
}


def action_display_label(action_id: str) -> str:
    return ACTION_DISPLAY_LABELS.get(action_id, action_id)


def tab_label_for(logical: str) -> str | None:
    return GAME_TABS.get(logical)


def side_for(logical: str) -> str:
    return load_pages_map().get(logical, DEFAULT_SIDES.get(logical, logical))


def merge_discovered_pages(
    links: list[dict] | None,
    tabs: list[dict] | None,
) -> dict[str, str]:
    """Merge discovery output into logical → slug map (tabs preferred over legacy ?side=)."""
    merged = dict(DEFAULT_SIDES)
    if links:
        for link in links:
            side = (link.get("side") or "").strip()
            if not side:
                continue
            text = (link.get("text") or "").lower()
            for logical, keywords in NAV_LINKS.items():
                if any(k in text for k in keywords):
                    merged[logical] = side
                    break
    if tabs:
        for tab in tabs:
            label = (tab.get("label") or "").lower()
            for logical, game_label in GAME_TABS.items():
                if game_label.lower() in label or label in game_label.lower():
                    route = tab.get("route") or tab.get("data_url") or tab.get("href") or ""
                    p_match = re.search(r"[?&]p=([^&\"'#]+)", route, re.I)
                    if p_match:
                        merged[logical] = p_match.group(1)
                    break
            route = tab.get("route") or tab.get("data_url") or tab.get("href") or ""
            p_match = re.search(r"[?&]p=([^&\"'#]+)", route, re.I)
            if p_match:
                logical = TAB_FRAME_ROUTES.get(p_match.group(1).lower())
                if logical:
                    merged[logical] = p_match.group(1)
    return merged


def save_pages_map(
    sides: dict[str, str],
    *,
    discovered_links: list[dict] | None = None,
    discovered_tabs: list[dict] | None = None,
    tab_labels: dict[str, str] | None = None,
) -> Path:
    path = get_pages_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"sides": sides, "game_url": "https://mafiaspillet.no/ms.php"}
    if discovered_links is not None:
        payload["discovered_links"] = discovered_links
    if discovered_tabs is not None:
        payload["discovered_tabs"] = discovered_tabs
    if tab_labels is not None:
        payload["tab_labels"] = tab_labels
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
