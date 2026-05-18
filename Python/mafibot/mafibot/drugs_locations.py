"""Drug trade cities — buy/sell only valid in specific locations."""

from __future__ import annotations

from mafibot.config import BotProfile

DEFAULT_DRUGS_BUY_CITY = "Kabul"

DEFAULT_DRUGS_SELL_CITIES: tuple[str, ...] = (
    "New York",
    "Oslo",
    "Detroit",
    "Rio",
    "Las Vegas",
)

_sell_city_index = 0


def drugs_enabled(profile: BotProfile) -> bool:
    return "drugs" in profile.economy_order


def drugs_buy_city(profile: BotProfile) -> str:
    city = (profile.drugs_buy_city or "").strip()
    return city or DEFAULT_DRUGS_BUY_CITY


def drugs_sell_cities(profile: BotProfile) -> list[str]:
    cities = [c.strip() for c in profile.drugs_sell_cities if c.strip()]
    return cities if cities else list(DEFAULT_DRUGS_SELL_CITIES)


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


def location_matches_city(location: str | None, city: str) -> bool:
    loc = _norm(location)
    target = _norm(city)
    if not loc or not target:
        return False
    return loc == target or target in loc or loc in target


def is_in_buy_city(location: str | None, profile: BotProfile) -> bool:
    return location_matches_city(location, drugs_buy_city(profile))


def is_in_sell_city(location: str | None, profile: BotProfile) -> bool:
    return any(location_matches_city(location, c) for c in drugs_sell_cities(profile))


def pick_sell_destination(profile: BotProfile) -> str:
    global _sell_city_index
    cities = drugs_sell_cities(profile)
    if not cities:
        return DEFAULT_DRUGS_SELL_CITIES[0]
    city = cities[_sell_city_index % len(cities)]
    _sell_city_index += 1
    return city


def drugs_destination_needed(profile: BotProfile, location: str | None) -> str | None:
    """
    City to travel to before drugs can run, or None if already in a valid location.
    """
    if not drugs_enabled(profile):
        return None

    prefer = profile.drugs_prefer
    if prefer == "buy":
        if is_in_buy_city(location, profile):
            return None
        return drugs_buy_city(profile)

    if prefer == "sell":
        if is_in_sell_city(location, profile):
            return None
        return pick_sell_destination(profile)

    # any: valid in buy city (buy) or sell city (sell)
    if is_in_buy_city(location, profile) or is_in_sell_city(location, profile):
        return None
    return drugs_buy_city(profile)


def location_allows_drugs(profile: BotProfile, location: str | None) -> bool:
    if not drugs_enabled(profile):
        return False
    prefer = profile.drugs_prefer
    if prefer == "buy":
        return is_in_buy_city(location, profile)
    if prefer == "sell":
        return is_in_sell_city(location, profile)
    return is_in_buy_city(location, profile) or is_in_sell_city(location, profile)


def drugs_click_labels_for_location(profile: BotProfile, location: str | None) -> tuple[str, ...]:
    prefer = profile.drugs_prefer
    if prefer == "buy":
        return ("kjøp",)
    if prefer == "sell":
        return ("selg",)
    if is_in_buy_city(location, profile):
        return ("kjøp",)
    if is_in_sell_city(location, profile):
        return ("selg",)
    return ("kjøp", "selg", "narkotika")
