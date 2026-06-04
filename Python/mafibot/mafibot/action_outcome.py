"""Parse reward lines from page text after an action."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MONEY_GAIN = re.compile(
    r"(?:fikk|tjente|vunnet|mottok|overført)\s+(?:deg\s+)?([\d\s]+)\s*kr",
    re.I,
)
_MONEY_LOSS = re.compile(
    r"(?:mistet|tapte|betalt|kostet)\s+(?:deg\s+)?([\d\s]+)\s*kr",
    re.I,
)
_POENG_GAIN = re.compile(
    r"(?:fikk|tjente|\+)\s*([\d\s]+)\s*(?:rank)?poeng",
    re.I,
)
_GRAM_CANNABIS = re.compile(
    r"([\d\s]+)\s*gram(?:mer)?\s+cannabis",
    re.I,
)
_GRAM_OPIUM = re.compile(
    r"([\d\s]+)\s*gram(?:mer)?\s+opium",
    re.I,
)
_SOLD_CANNABIS = re.compile(
    r"selg(?:te|er)?\s+([\d\s]+)\s*gram(?:mer)?\s+cannabis|"
    r"cannabis[^.\n]{0,40}([\d\s]+)\s*gram",
    re.I,
)
_SOLD_OPIUM = re.compile(
    r"selg(?:te|er)?\s+([\d\s]+)\s*gram(?:mer)?\s+opium|"
    r"opium[^.\n]{0,40}([\d\s]+)\s*gram",
    re.I,
)


def _parse_int(m: re.Match[str]) -> int:
    raw = None
    for i in range(1, (m.lastindex or 0) + 1):
        g = m.group(i)
        if g and str(g).strip():
            raw = g
            break
    if not raw:
        return 0
    return int(re.sub(r"\s+", "", str(raw)))


@dataclass
class OutcomeHints:
    money_delta: int = 0
    rank_delta: int = 0
    cannabis_grams: int = 0
    opium_grams: int = 0


def parse_action_outcome(
    text: str,
    *,
    action: str = "",
    source: str = "",
) -> OutcomeHints:
    """Best-effort parse of Norwegian outcome messages on the current page."""
    del action, source  # reserved for future action-specific patterns
    hints = OutcomeHints()
    if not text:
        return hints

    money = 0
    for m in _MONEY_GAIN.finditer(text):
        money += _parse_int(m)
    for m in _MONEY_LOSS.finditer(text):
        money -= _parse_int(m)
    hints.money_delta = money

    rank = 0
    for m in _POENG_GAIN.finditer(text):
        rank += _parse_int(m)
    hints.rank_delta = rank

    cannabis = 0
    for pat in (_GRAM_CANNABIS, _SOLD_CANNABIS):
        for m in pat.finditer(text):
            cannabis += _parse_int(m)
    hints.cannabis_grams = cannabis

    opium = 0
    for pat in (_GRAM_OPIUM, _SOLD_OPIUM):
        for m in pat.finditer(text):
            opium += _parse_int(m)
    hints.opium_grams = opium

    return hints
