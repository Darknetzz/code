"""Paths, bot profiles, and runtime settings."""

from __future__ import annotations

import json
import os
import sys
from datetime import time
from pathlib import Path
from typing import Literal

DrugsPrefer = Literal["any", "buy", "sell"]
MarketMode = Literal["none", "sell_junk", "buy_supplies"]
CrimeKind = Literal["perform", "steal"]
CrimePerformType = Literal["lett", "tung", "any"]
CrimeStealTargetMode = Literal["random", "specific"]

from pydantic import BaseModel, Field

BASE_URL = "https://mafiaspillet.no/"
GAME_URL = "https://mafiaspillet.no/ms.php"
DEFAULT_PROFILE_NAME = "ranker"

BuildStyle = Literal["ranker", "okonom", "angriper"]
SchedulerMode = Literal["priority", "soonest_ready"]
MissionsMode = Literal["off", "start_only", "auto_progress"]
MinionsAction = Literal["disabled", "train", "collect_reports_only"]
MurderMode = Literal["static_targets", "report_stream", "retaliate_only"]
OrganizedCrimeDifficulty = Literal["auto", "lett", "medium", "hard"]


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
    scheduler: SchedulerMode = Field(
        default="priority",
        description="priority: economy_order first match; soonest_ready: pick ready action with nearest cooldown end",
    )
    stop_webhook_url: str = Field(
        default="",
        description="Optional Discord-compatible webhook URL when session stops (captcha/ban/logout)",
    )
    assist_webhook_url: str = Field(
        default="",
        description="Optional webhook for assist alerts (war/kidnap); falls back to stop_webhook_url",
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
    hotel_min_wallet: int = Field(
        default=500,
        ge=0,
        description="Skip hotel booking when wallet (Penger) is below this",
    )
    hotel_book_when_broke: bool = False
    hotel_max_nightly_cost: int | None = Field(
        default=None,
        ge=0,
        description="Skip booking when parsed nightly room cost exceeds this",
    )
    hotel_fallback_when_blocked: bool = Field(
        default=True,
        description="Disable stay_in_hotel for rest of session after repeated book failures",
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
    # Murder
    murder_targets: list[str] = Field(default_factory=list)
    murder_rotate_targets: bool = False
    murder_mode: MurderMode = Field(
        default="static_targets",
        description="static_targets: murder_targets list; report_stream: orange reports; retaliate_only: incoming shots",
    )
    murder_actually_shoot: bool = True
    murder_min_attack_margin: int = Field(
        default=0,
        ge=0,
        description="Require attack >= target protection + margin when protection is known",
    )
    murder_travel_before_shoot: bool = True
    pause_on_restricted_status: bool = Field(
        default=True,
        description="Skip gameplay when feriemodus, kidnapped, or startbeskyttelse",
    )
    assist_webhook_on_war: bool = False
    assist_webhook_on_kidnap: bool = False
    jail_wait_min_sec: float = Field(
        default=300.0,
        ge=60.0,
        description="Min sleep when in jail (nothing to do)",
    )
    jail_wait_max_sec: float = Field(
        default=900.0,
        ge=120.0,
        description="Max sleep when in jail",
    )
    hospital_idle_wait_min_sec: float = Field(
        default=120.0,
        ge=30.0,
        description="Min sleep when in hospital and no actions runnable",
    )
    hospital_idle_wait_max_sec: float = Field(
        default=300.0,
        ge=60.0,
        description="Max sleep when in hospital and idle",
    )
    # Messages
    messages_interval_minutes: int = 0
    messages_only_when_unread: bool = False
    messages_max_per_hour: int = Field(default=8, ge=0, le=60)
    # Family
    family_interval_minutes: int = 0
    family_auto_accept: bool = True
    # Crime (optional overrides)
    crime_min_health_percent: int | None = None
    crime_actions: list[str] = Field(
        default_factory=list,
        description="Enabled sections: enkel, tung, stjel (one or more)",
    )
    crime_enkel_choices: list[str] = Field(
        default_factory=list,
        description="Enkel crime option ids; empty = any in section",
    )
    crime_tung_choices: list[str] = Field(
        default_factory=list,
        description="Tung crime option ids; empty = any in section",
    )
    crime_steal_items: list[str] = Field(
        default_factory=lambda: ["penger"],
        description="Stjel item ids: garasje, vapen, penger",
    )
    crime_rotate_actions: bool = True
    # Legacy (migrated to crime_actions / choices when unset)
    crime_kind: CrimeKind = "perform"
    crime_perform_type: CrimePerformType = "any"
    crime_steal_what: str = "penger"
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
    # Business / ship / work gating
    work_only_when_ready: bool = True
    business_only_when_income_ready: bool = True
    ship_only_when_in_port: bool = True
    # Ship: where to send skip (Mitt rederi) — routes keyed by current city/port
    ship_destinations: list[str] = Field(
        default_factory=list,
        description="Fallback destinations when no ship_routes entry matches location",
    )
    ship_routes: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Origin city/port → ordered destination harbors",
    )
    ship_rotate_destinations: bool = False
    # Sykehus — visit when health % is below threshold (action must be in economy_order)
    hospital_health_threshold: int = Field(
        default=80,
        ge=1,
        le=99,
        description="Run hospital when Helse is below this percent",
    )
    # Minions (Undersåtter)
    minions_enabled: bool = False
    minions_action: MinionsAction = "train"
    minions_train_when_ready: bool = True
    # Missions (Oppdrag)
    missions_enabled: bool = False
    missions_auto_start: bool = True
    missions_mode: MissionsMode = "start_only"
    missions_prioritize_when_incomplete: bool = True
    # Organized crime
    organized_crime_enabled: bool = False
    organized_crime_min_health_percent: int | None = None
    organized_crime_difficulty: OrganizedCrimeDifficulty = "auto"
    # Market (Marked)
    market_enabled: bool = False
    market_mode: MarketMode = "none"
    market_max_per_hour: int = Field(default=4, ge=0, le=30)
    market_sell_items: list[str] = Field(default_factory=list)
    market_buy_items: list[str] = Field(default_factory=list)
    market_buy_when_mission_needs: bool = True
    # Travel rotation (anti-surveillance)
    travel_rotate_cities: bool = False
    travel_city_pool: list[str] = Field(default_factory=list)
    travel_rotate_min_minutes: int = Field(default=45, ge=5)
    # Scheduler boosts
    scheduler_happy_hour_boost: bool = True
    scheduler_city_income_boost: bool = True


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
    from mafibot.profile_migrate import migrate_crime_fields

    stem = (name or DEFAULT_PROFILE_NAME).strip()
    for base in (get_profiles_dir(), bundled_profiles_dir()):
        path = base / f"{stem}.json"
        if path.is_file():
            data = migrate_crime_fields(json.loads(path.read_text(encoding="utf-8")))
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
