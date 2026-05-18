"""Ship (skip) send destinations — routes depend on current port/location."""

from __future__ import annotations

import re

from mafibot.config import BotProfile
from mafibot.drugs_locations import location_matches_city

_route_index: dict[str, int] = {}


def parse_ship_routes_text(text: str) -> dict[str, list[str]]:
    """
    Parse lines like ``Kabul: Oslo, New York`` or ``Oslo -> Detroit``.
    """
    routes: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        origin: str
        dest_part: str
        if ":" in line:
            origin, dest_part = line.split(":", 1)
        elif "->" in line:
            origin, dest_part = line.split("->", 1)
        else:
            continue
        origin = origin.strip()
        dests = [d.strip() for d in re.split(r"[,|]", dest_part) if d.strip()]
        if origin and dests:
            routes[origin] = dests
    return routes


def format_ship_routes_text(routes: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for origin in sorted(routes.keys(), key=str.casefold):
        dests = routes[origin]
        if dests:
            lines.append(f"{origin}: {', '.join(dests)}")
    return "\n".join(lines)


def _norm_key(location: str | None) -> str:
    return (location or "").strip().lower() or "_"


def destinations_for_location(
    profile: BotProfile, location: str | None
) -> list[str]:
    """Destinations to try when sending a ship from *location*."""
    for origin, dests in (profile.ship_routes or {}).items():
        if location_matches_city(location, origin):
            return [d.strip() for d in dests if d.strip()]
    return [d.strip() for d in profile.ship_destinations if d.strip()]


def pick_ship_destinations(profile: BotProfile, location: str | None) -> list[str]:
    """Ordered harbor/city names to click on the rederi page."""
    dests = destinations_for_location(profile, location)
    if not dests or not profile.ship_rotate_destinations:
        return dests
    key = _norm_key(location)
    idx = _route_index.get(key, 0)
    start = idx % len(dests)
    _route_index[key] = idx + 1
    return dests[start:] + dests[:start]


def ship_send_configured(profile: BotProfile) -> bool:
    return bool(profile.ship_routes) or bool(profile.ship_destinations)
