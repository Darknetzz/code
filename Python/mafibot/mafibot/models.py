"""Pydantic models for REST API and WebSocket payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field

from mafibot.config import BotProfile


class BotProfileDocument(BotProfile):
    """Serializable bot profile (same fields as BotProfile)."""


class GameStateResponse(BaseModel):
    logged_in: bool = False
    in_hotel: bool = False
    hotel_blocks_actions: bool = False
    money: int | None = None
    health_percent: int | None = None
    location: str | None = None
    crime_ready: bool = False
    player_name: str | None = None


class CredentialsUpdate(BaseModel):
    user: str = ""
    password: str = ""


class CredentialsStatus(BaseModel):
    has_user: bool = False
    has_password: bool = False
    env_path: str = ""


class RunRequest(BaseModel):
    profile: str = "ranker"
    max_minutes: int | None = None
    dry_run: bool = False
    accept_tos: bool = False
    headless: bool = False
    channel: str | None = "chrome"


class LoginRequest(BaseModel):
    timeout_sec: float = 600
    headless: bool = False
    channel: str | None = "chrome"


class DiscoverRequest(BaseModel):
    headless: bool = False
    channel: str | None = "chrome"
    accept_tos: bool = False


class RunStatusResponse(BaseModel):
    state: str
    profile: str | None = None
    dry_run: bool = False
    elapsed_sec: float | None = None
    last_action: str | None = None
    last_message: str | None = None
    last_reason: str | None = None
    error: str | None = None
    game: GameStateResponse = Field(default_factory=GameStateResponse)


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
