"""Pydantic models for REST API and WebSocket payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field

from mafibot.config import BotProfile


class BotProfileDocument(BotProfile):
    """Serializable bot profile (same fields as BotProfile)."""


class ProfileListItem(BaseModel):
    name: str
    is_bundled: bool = False
    has_user_copy: bool = False
    deletable: bool = False


class ProfileCreateRequest(BaseModel):
    name: str
    copy_from: str | None = None


class ProfileRenameRequest(BaseModel):
    new_name: str


class ActiveCooldownResponse(BaseModel):
    id: str
    label: str
    ready_at: str | None = None
    remaining_sec: float | None = None
    raw: str = ""


class ReportEntryResponse(BaseModel):
    username: str
    city: str | None = None
    null_delay: bool = False
    incoming_shot: bool = False


class MinionInfoResponse(BaseModel):
    id: str | None = None
    name: str
    alive: bool = True
    training: str | None = None


class MinionsScanResponse(BaseModel):
    total: int = 0
    alive: int = 0
    dead: int = 0
    minions: list[MinionInfoResponse] = Field(default_factory=list)


class GameStateResponse(BaseModel):
    logged_in: bool = False
    in_hotel: bool = False
    hotel_blocks_actions: bool = False
    money: int | None = None
    health_percent: int | None = None
    location: str | None = None
    crime_ready: bool = False
    crime_enkel_ready: bool = True
    crime_tung_ready: bool = True
    crime_stjel_ready: bool = True
    player_name: str | None = None
    attack: int | None = None
    protection: int | None = None
    rank_name: str | None = None
    happy_hour_active: bool = False
    happy_hour_buffs: list[str] = Field(default_factory=list)
    mission_number: int | None = None
    mission_progress_current: int | None = None
    mission_progress_total: int | None = None
    mission_requirement_hint: str | None = None
    feriemodus: bool = False
    startbeskyttelse: bool = False
    kidnapped: bool = False
    family_war_active: bool = False
    minions_train_ready: bool = False
    report_entries: list[ReportEntryResponse] = Field(default_factory=list)
    active_cooldowns: list[ActiveCooldownResponse] = Field(default_factory=list)


class CredentialsUpdate(BaseModel):
    user: str = ""
    password: str = ""


class CredentialsStatus(BaseModel):
    has_user: bool = False
    has_password: bool = False
    user: str = ""
    env_path: str = ""


class RunRequest(BaseModel):
    profile: str = "ranker"
    max_minutes: int | None = None
    dry_run: bool = False
    accept_tos: bool = False
    headless: bool = False
    channel: str | None = "chrome"
    skip_preflight: bool = False
    require_verification: bool = False


class LoginRequest(BaseModel):
    timeout_sec: float = 600
    headless: bool = False
    channel: str | None = "chrome"


class DiscoverRequest(BaseModel):
    headless: bool = False
    channel: str | None = "chrome"
    accept_tos: bool = False
    compare_last: bool = False


class SessionMetricsResponse(BaseModel):
    profile: str = ""
    started_at: str = ""
    ended_at: str = ""
    dry_run: bool = False
    actions_run: int = 0
    actions_failed: int = 0
    actions_skipped: int = 0
    parse_failures: int = 0
    hotel_book_failures: int = 0
    hotel_skip_insufficient_funds: int = 0
    hotel_skip_hotel_full: int = 0
    hotel_skip_wallet_low: int = 0
    samples_in_hotel: int = 0
    samples_out_hotel: int = 0
    money_start: int | None = None
    money_end: int | None = None
    rank_start: int | None = None
    rank_end: int | None = None
    stop_reason: str | None = None
    hotel_time_percent: float | None = None
    rank_points_gained: int | None = None
    action_counts: dict[str, int] = Field(default_factory=dict)


class PreflightCheckResponse(BaseModel):
    id: str
    ok: bool
    message: str
    hint: str = ""


class PreflightResponse(BaseModel):
    ok: bool
    checks: list[PreflightCheckResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    verification: dict | None = None


class RunStatusResponse(BaseModel):
    state: str
    profile: str | None = None
    dry_run: bool = False
    elapsed_sec: float | None = None
    last_action: str | None = None
    last_message: str | None = None
    last_reason: str | None = None
    idle_detail: str | None = None
    parse_error: dict[str, str | None] | None = None
    parse_playbook: str | None = None
    error: str | None = None
    game: GameStateResponse = Field(default_factory=GameStateResponse)
    dry_run_decisions: list[dict[str, str | None]] = Field(default_factory=list)
    session_metrics: SessionMetricsResponse | None = None


class SessionStatusResponse(BaseModel):
    browser_open: bool = False
    logged_in: bool = False
    game: GameStateResponse = Field(default_factory=GameStateResponse)


class HealthResponse(BaseModel):
    version: str
    playwright: bool
    config_dir: str
    profiles_dir: str
    profile_dir: str


class LogAppendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class LogLinesResponse(BaseModel):
    path: str
    lines: list[str] = Field(default_factory=list)
