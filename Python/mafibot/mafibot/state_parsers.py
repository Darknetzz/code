"""Extract extended game signals from page text (tests + live parse)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Happy Hour buff ids (help: hjelp.mafiaspillet.no happy hour list)
HAPPY_HOUR_BUFFS: tuple[str, ...] = (
    "double_crime_rank",
    "half_crime_cooldown",
    "half_steal_cooldown",
    "half_fly_cooldown",
    "half_club_cooldown",
    "half_train_minions",
    "double_frakt_rank",
    "half_bullet_price",
    "crime_points",
    "ship_points",
    "kapring_reset",
    "stress_cases",
)

_HAPPY_HOUR_PATTERNS: dict[str, re.Pattern[str]] = {
    "double_crime_rank": re.compile(
        r"dobbel{1,2}t?\s+rankpoeng|2\s*x\s+rankpoeng", re.I
    ),
    "half_crime_cooldown": re.compile(
        r"halvert\s+ventetid\s+(?:enkel|tung|krim)|halv(?:ert)?\s+ventetid\s+enkel",
        re.I,
    ),
    "half_steal_cooldown": re.compile(r"halvert\s+ventetid\s+stjel", re.I),
    "half_fly_cooldown": re.compile(r"halvert\s+ventetid\s+fly", re.I),
    "half_club_cooldown": re.compile(r"halvert\s+ventetid\s+club", re.I),
    "half_train_minions": re.compile(r"halvert\s+ventetid\s+trene\s+mine\s+folk", re.I),
    "double_frakt_rank": re.compile(r"50\s*%\s*mer\s+rankpoeng\s+frakt", re.I),
    "half_bullet_price": re.compile(r"halv\s+pris\s+skudd", re.I),
    "crime_points": re.compile(r"poeng\s+i\s+enkel\s+og\s+tung\s+krim", re.I),
    "ship_points": re.compile(r"poeng\s+i\s+skip", re.I),
    "kapring_reset": re.compile(r"ventetid\s+kapring\s+nullstilt", re.I),
    "stress_cases": re.compile(r"stresskoffer", re.I),
}

_ATTACK_PATTERN = re.compile(r"angrep[:\s]+(\d+)", re.I)
_PROTECTION_PATTERN = re.compile(r"beskyttelse[:\s]+(\d+)", re.I)
_RANK_NAME_PATTERN = re.compile(r"rank[:\s]+([^\n]+)", re.I)
_MISSION_NUM_PATTERN = re.compile(r"oppdrag\s*#?\s*(\d+)", re.I)
_MISSION_PROGRESS_PATTERN = re.compile(
    r"(\d+)\s*/\s*(\d+)\s*(?:kriminell|handling|gang|trening|bedrift|undersått)",
    re.I,
)
_FERIE_PATTERN = re.compile(r"feriemodus|ferie\s+modus", re.I)
_START_PROTECTION_PATTERN = re.compile(r"startbeskyttelse|start\s+beskyttelse", re.I)
_KIDNAPPED_PATTERN = re.compile(
    r"kidnappet|du\s+er\s+holdt\s+fanget|holdt\s+fanget", re.I
)
_FAMILY_WAR_PATTERN = re.compile(
    r"familiekrig|krig\s+mot|i\s+krig\s+med", re.I
)
_MINIONS_TRAIN_READY_PATTERN = re.compile(
    r"trene[^.\n]{0,40}(?:klar!|kan\s+trene)|klar!\s*trene", re.I
)
_CRIME_SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "enkel": re.compile(
        r"enkel\s+kriminalitet[^.\n]{0,80}(?:klar!|kan\s+utføre)|"
        r"lett\s+kriminalitet[^.\n]{0,80}(?:klar!|kan)",
        re.I,
    ),
    "tung": re.compile(
        r"tung\s+kriminalitet[^.\n]{0,80}(?:klar!|kan\s+utføre)", re.I
    ),
    "stjel": re.compile(r"\bstjel\b[^.\n]{0,60}(?:klar!|kan\s+stjel)", re.I),
}
_CRIME_SECTION_COOLDOWN: dict[str, re.Pattern[str]] = {
    "enkel": re.compile(
        r"enkel\s+kriminalitet[^.\n]{0,80}(?:vente|må\s+vente|\d+\s*min)", re.I
    ),
    "tung": re.compile(
        r"tung\s+kriminalitet[^.\n]{0,80}(?:vente|må\s+vente|\d+\s*min)", re.I
    ),
    "stjel": re.compile(r"\bstjel\b[^.\n]{0,60}(?:vente|må\s+vente|\d+\s*min)", re.I),
}

_REPORT_LINE_PATTERN = re.compile(
    r"(?P<user>[A-Za-z0-9_\-.]{2,24})\s+(?:i\s+)?(?P<city>[A-ZÆØÅ][a-zæøå]+(?:\s+[A-ZÆØÅ][a-zæøå]+)?)",
    re.I,
)
_ORANGE_REPORT_PATTERN = re.compile(r"null\s*delay|orange|oransje", re.I)
_INCOMING_SHOT_PATTERN = re.compile(
    r"skjøt\s+på\s+deg|skudd\s+mot\s+deg|har\s+skutt\s+på\s+deg", re.I
)


@dataclass
class ReportEntry:
    username: str
    city: str | None = None
    null_delay: bool = False
    incoming_shot: bool = False


@dataclass
class ParsedExtendedState:
    attack: int | None = None
    protection: int | None = None
    rank_name: str | None = None
    happy_hour_buffs: list[str] = field(default_factory=list)
    happy_hour_active: bool = False
    mission_number: int | None = None
    mission_progress_current: int | None = None
    mission_progress_total: int | None = None
    mission_requirement_hint: str | None = None
    feriemodus: bool = False
    startbeskyttelse: bool = False
    kidnapped: bool = False
    family_war_active: bool = False
    minions_train_ready: bool = False
    crime_enkel_ready: bool | None = None
    crime_tung_ready: bool | None = None
    crime_stjel_ready: bool | None = None
    report_entries: list[ReportEntry] = field(default_factory=list)


def parse_happy_hour_buffs(text: str) -> list[str]:
    if not re.search(r"happy\s*hour", text, re.I):
        return []
    active: list[str] = []
    for buff_id, pattern in _HAPPY_HOUR_PATTERNS.items():
        if pattern.search(text):
            active.append(buff_id)
    return active


def parse_attack_protection(text: str) -> tuple[int | None, int | None]:
    attack = protection = None
    am = _ATTACK_PATTERN.search(text)
    if am:
        attack = int(am.group(1))
    pm = _PROTECTION_PATTERN.search(text)
    if pm:
        protection = int(pm.group(1))
    return attack, protection


def parse_mission_fields(text: str) -> tuple[
    int | None,
    int | None,
    int | None,
    str | None,
]:
    num = None
    m = _MISSION_NUM_PATTERN.search(text)
    if m:
        num = int(m.group(1))
    current = total = None
    pm = _MISSION_PROGRESS_PATTERN.search(text)
    if pm:
        current = int(pm.group(1))
        total = int(pm.group(2))
    hint = None
    lower = text.lower()
    if "kriminell" in lower and "handling" in lower:
        hint = "crime"
    elif "trene" in lower and "undersått" in lower:
        hint = "minions_train"
    elif "våpen" in lower or "skytevåpen" in lower:
        hint = "buy_weapon"
    elif "bil" in lower and "kjøp" in lower:
        hint = "buy_car"
    elif "bedrift" in lower:
        hint = "business"
    elif "rederi" in lower or "skip" in lower:
        hint = "ship"
    elif "fly" in lower or "flyplass" in lower:
        hint = "travel"
    elif "club" in lower or "lucha" in lower:
        hint = "club"
    elif "drepe" in lower or "skyt" in lower:
        hint = "murder"
    return num, current, total, hint


def parse_crime_section_ready(text: str, section: str, global_ready: bool) -> bool:
    if not global_ready:
        return False
    ready_pat = _CRIME_SECTION_PATTERNS.get(section)
    cd_pat = _CRIME_SECTION_COOLDOWN.get(section)
    if ready_pat and ready_pat.search(text):
        return True
    if cd_pat and cd_pat.search(text):
        return False
    return global_ready


def parse_report_stream(text: str) -> list[ReportEntry]:
    entries: list[ReportEntry] = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        if not any(
            kw in line.lower()
            for kw in ("rapport", "overvåk", "null delay", "skjøt", "skudd")
        ):
            continue
        null_delay = bool(_ORANGE_REPORT_PATTERN.search(line))
        incoming = bool(_INCOMING_SHOT_PATTERN.search(line))
        m = _REPORT_LINE_PATTERN.search(line)
        if m:
            entries.append(
                ReportEntry(
                    username=m.group("user"),
                    city=m.group("city"),
                    null_delay=null_delay,
                    incoming_shot=incoming,
                )
            )
        elif incoming:
            um = re.search(r"([A-Za-z0-9_\-.]{2,24})", line)
            if um:
                entries.append(
                    ReportEntry(
                        username=um.group(1),
                        city=None,
                        null_delay=null_delay,
                        incoming_shot=True,
                    )
                )
    return entries


def parse_extended_state(text: str, *, crime_ready: bool = True) -> ParsedExtendedState:
    attack, protection = parse_attack_protection(text)
    rank_name = None
    rm = _RANK_NAME_PATTERN.search(text)
    if rm:
        rank_name = rm.group(1).strip()
    happy = parse_happy_hour_buffs(text)
    mnum, mcur, mtot, hint = parse_mission_fields(text)
    return ParsedExtendedState(
        attack=attack,
        protection=protection,
        rank_name=rank_name,
        happy_hour_buffs=happy,
        happy_hour_active=bool(happy),
        mission_number=mnum,
        mission_progress_current=mcur,
        mission_progress_total=mtot,
        mission_requirement_hint=hint,
        feriemodus=bool(_FERIE_PATTERN.search(text)),
        startbeskyttelse=bool(_START_PROTECTION_PATTERN.search(text)),
        kidnapped=bool(_KIDNAPPED_PATTERN.search(text)),
        family_war_active=bool(_FAMILY_WAR_PATTERN.search(text)),
        minions_train_ready=bool(_MINIONS_TRAIN_READY_PATTERN.search(text)),
        crime_enkel_ready=parse_crime_section_ready(text, "enkel", crime_ready),
        crime_tung_ready=parse_crime_section_ready(text, "tung", crime_ready),
        crime_stjel_ready=parse_crime_section_ready(text, "stjel", crime_ready),
        report_entries=parse_report_stream(text),
    )
