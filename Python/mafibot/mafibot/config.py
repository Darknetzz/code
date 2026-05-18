"""Paths, bot profiles, and runtime settings."""

from __future__ import annotations

import json
import os
import sys
from datetime import time
from pathlib import Path
from typing import Literal

DrugsPrefer = Literal["any", "buy", "sell"]
CrimeKind = Literal["perform", "steal"]
CrimePerformType = Literal["lett", "tung", "any"]
CrimeStealTargetMode = Literal["random", "specific"]

from pydantic import BaseModel, Field

BASE_URL = "https://mafiaspillet.no/"
GAME_URL = "https://mafiaspillet.no/ms.php"
DEFAULT_PROFILE_NAME = "ranker"

BuildStyle = Literal["ranker", "okonom", "angriper"]


class PlayWindow(BaseModel):
    start_hour: int = 8
    end_hour: int = 23


class BotProfile(BaseModel):
    name: str = DEFAULT_PROFILE_NAME
    build: BuildStyle = "ranker"
    aggression: float = Field(default=0.3, ge=0.0, le=1.0)
    economy_order: list[str] = Field(
        default_factory=lambda: [
            "crime",
            "business",
            "ship",
            "travel",
            "drugs",
            "bank",
        ]
    )
    stay_in_hotel: bool = True
    book_hotel_before_action: bool = True
    book_hotel_after_every_action: bool = True
    book_hotel_when_idle: bool = True
    max_seconds_before_book_hotel: float = Field(
        default=2.0,
        ge=0.0,
        le=10.0,
        description="Max delay between gameplay action and book-hotel step",
    )
    social_interval_minutes: int = 45
    social_enabled: bool = True
    combat_enabled: bool = False
    min_health_percent: int = 35
    play_window: PlayWindow = Field(default_factory=PlayWindow)
    max_session_minutes: int = 120
    idle_chance: float = 0.1
    idle_min_minutes: float = 5.0
    idle_max_minutes: float = 15.0
    cooldown_jitter_min_sec: float = 30.0
    cooldown_jitter_max_sec: float = 120.0
    post_action_wait_min_sec: float = 8.0
    post_action_wait_max_sec: float = 25.0
    nothing_todo_wait_min_sec: float = 45.0
    nothing_todo_wait_max_sec: float = 180.0
    min_seconds_between_clicks: float = 2.8
    min_seconds_after_tab_change: float = 3.5
    # Bank: keep wallet (Penger) near target via deposit/withdraw
    bank_auto_balance: bool = False
    bank_keep_cash_on_hand: int = Field(
        default=100_000,
        ge=0,
        description="Target cash to keep in wallet (Penger)",
    )
    bank_balance_tolerance: int = Field(
        default=25_000,
        ge=0,
        description="Only transfer when wallet is farther than this from target",
    )
    # Murder: must set at least one username or murder never runs
    murder_targets: list[str] = Field(default_factory=list)
    murder_rotate_targets: bool = False
    # Messages
    messages_interval_minutes: int = 0
    messages_only_when_unread: bool = False
    messages_max_per_hour: int = Field(default=8, ge=0, le=60)
    # Family
    family_interval_minutes: int = 0
    family_auto_accept: bool = True
    # Crime (optional overrides)
    crime_min_health_percent: int | None = None
    crime_kind: CrimeKind = "perform"
    crime_perform_type: CrimePerformType = "any"
    crime_steal_what: str = "bil"
    crime_steal_target_mode: CrimeStealTargetMode = "random"
    crime_steal_username: str = ""
    crime_button_labels: list[str] = Field(
        default_factory=list,
        description="Optional submit-button label override (comma-separated in UI)",
    )
    # Travel
    travel_destinations: list[str] = Field(default_factory=list)
    # Drugs (buy/sell only in specific cities — requires travel)
    drugs_prefer: DrugsPrefer = "any"
    drugs_buy_city: str = "Kabul"
    drugs_sell_cities: list[str] = Field(
        default_factory=lambda: [
            "New York",
            "Oslo",
            "Detroit",
            "Rio",
            "Las Vegas",
        ]
    )
    # Business / ship gating
    business_only_when_income_ready: bool = True
    ship_only_when_in_port: bool = True


def get_config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "mafibot"


def get_profile_dir() -> Path:
    return get_config_dir() / "profile"


def get_discovery_dir() -> Path:
    return get_config_dir() / "discovery"


def get_profiles_dir() -> Path:
    return get_config_dir() / "profiles"


def get_pages_config_path() -> Path:
    return get_config_dir() / "pages.json"


def bundled_profiles_dir() -> Path:
    return Path(__file__).resolve().parent / "profiles"


def load_bot_profile(name: str | None = None) -> BotProfile:
    stem = (name or DEFAULT_PROFILE_NAME).strip()
    for base in (get_profiles_dir(), bundled_profiles_dir()):
        path = base / f"{stem}.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return BotProfile.model_validate(data)
    if stem != DEFAULT_PROFILE_NAME:
        return load_bot_profile(DEFAULT_PROFILE_NAME)
    return BotProfile(name=stem)


def in_play_window(profile: BotProfile) -> bool:
    from datetime import datetime

    now = datetime.now().time()
    start = time(profile.play_window.start_hour, 0)
    end = time(profile.play_window.end_hour, 0)
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (
        Path.cwd() / ".env",
        get_config_dir() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ):
        if path.is_file():
            load_dotenv(path)
            return
