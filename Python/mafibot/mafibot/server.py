"""FastAPI local dashboard for Mafibot."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from mafibot import __version__
from mafibot.config import get_config_dir, get_profile_dir, get_profiles_dir
from mafibot.config_store import (
    get_credentials_status,
    list_profile_names,
    load_profile_document,
    save_credentials,
    save_profile_document,
)
from mafibot.models import (
    BotProfileDocument,
    CredentialsStatus,
    CredentialsUpdate,
    DiscoverRequest,
    GameStateResponse,
    HealthResponse,
    LoginRequest,
    RunRequest,
    RunStatusResponse,
    SessionStatusResponse,
)
from mafibot.runner import MafibotRunner, get_runner, run_state_blocks_start

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Mafibot", description="Mafiaspillet autopilot dashboard")

_ws_clients: list[WebSocket] = []


def _status_response(runner: MafibotRunner) -> RunStatusResponse:
    st = runner.status
    return RunStatusResponse(
        state=st.state.value,
        profile=st.profile,
        dry_run=st.dry_run,
        elapsed_sec=st.elapsed_sec(),
        last_action=st.last_action,
        last_message=st.last_message,
        last_reason=st.last_reason,
        error=st.error,
        game=GameStateResponse(**st.game.__dict__),
    )


async def _broadcast(message: dict) -> None:
    payload = json.dumps(message)
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


def _status_payload() -> dict:
    data = _status_response(get_runner()).model_dump()
    return {"type": "status", **data}


def _runner_log_handler(message: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_broadcast({"type": "log", "message": message}))


def _runner_status_handler(_status: object) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_broadcast(_status_payload()))


_runner_hooked = False


def _ensure_runner_hooks() -> None:
    global _runner_hooked
    if not _runner_hooked:
        runner = get_runner()
        runner.add_log_handler(_runner_log_handler)
        runner.add_status_handler(_runner_status_handler)
        _runner_hooked = True


@app.on_event("startup")
def _startup() -> None:
    _ensure_runner_hooks()


@app.get("/api/health", response_model=HealthResponse)
def api_health() -> HealthResponse:
    try:
        import playwright  # noqa: F401

        pw = True
    except ImportError:
        pw = False
    return HealthResponse(
        version=__version__,
        playwright=pw,
        config_dir=str(get_config_dir()),
        profiles_dir=str(get_profiles_dir()),
        profile_dir=str(get_profile_dir()),
    )


@app.get("/api/profiles")
def api_list_profiles() -> list[str]:
    return list_profile_names()


@app.get("/api/profiles/{name}", response_model=BotProfileDocument)
def api_get_profile(name: str) -> BotProfileDocument:
    try:
        return load_profile_document(name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/profiles/{name}", response_model=BotProfileDocument)
def api_put_profile(name: str, doc: BotProfileDocument) -> BotProfileDocument:
    doc.name = name.strip()
    try:
        return save_profile_document(doc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/credentials", response_model=CredentialsStatus)
def api_get_credentials() -> CredentialsStatus:
    return get_credentials_status()


@app.put("/api/credentials", response_model=CredentialsStatus)
def api_put_credentials(body: CredentialsUpdate) -> CredentialsStatus:
    return save_credentials(body)


@app.get("/api/session", response_model=SessionStatusResponse)
async def api_session() -> SessionStatusResponse:
    runner = get_runner()
    game = await runner.refresh_session_snapshot()
    return SessionStatusResponse(
        browser_open=runner.page is not None,
        logged_in=game.logged_in,
        game=GameStateResponse(**game.__dict__),
    )


@app.get("/api/run/status", response_model=RunStatusResponse)
def api_run_status() -> RunStatusResponse:
    return _status_response(get_runner())


@app.post("/api/run")
async def api_start_run(req: RunRequest) -> dict:
    _ensure_runner_hooks()
    runner = get_runner()
    if run_state_blocks_start(runner.status.state):
        raise HTTPException(status_code=409, detail="A task is already in progress")
    if not req.accept_tos:
        raise HTTPException(status_code=400, detail="accept_tos is required")

    try:
        await runner.start_run(
            req.profile,
            max_minutes=req.max_minutes,
            dry_run=req.dry_run,
            accept_tos=req.accept_tos,
            headless=req.headless,
            channel=req.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def _watch() -> None:
        try:
            if runner._task:
                await runner._task
        except Exception:
            pass
        await _broadcast(_status_payload())

    asyncio.create_task(_watch())
    await _broadcast(_status_payload())
    return {"ok": True, "message": "Run started"}


@app.post("/api/stop")
async def api_stop() -> dict:
    await get_runner().stop()
    await _broadcast(_status_payload())
    return {"ok": True}


@app.post("/api/login")
async def api_login(req: LoginRequest) -> dict:
    _ensure_runner_hooks()
    runner = get_runner()
    if run_state_blocks_start(runner.status.state):
        raise HTTPException(status_code=409, detail="A task is already in progress")
    await runner.start_login(
        timeout_sec=req.timeout_sec,
        headless=req.headless,
        channel=req.channel,
    )

    async def _watch() -> None:
        try:
            if runner._task:
                await runner._task
        except Exception:
            pass
        await _broadcast(_status_payload())

    asyncio.create_task(_watch())
    await _broadcast(_status_payload())
    return {"ok": True, "message": "Login browser opened"}


@app.post("/api/login/done")
async def api_login_done() -> dict:
    await get_runner().finish_login()
    await _broadcast(_status_payload())
    return {"ok": True, "message": "Closing login browser"}


@app.post("/api/discover")
async def api_discover(req: DiscoverRequest) -> dict:
    _ensure_runner_hooks()
    runner = get_runner()
    if run_state_blocks_start(runner.status.state):
        raise HTTPException(status_code=409, detail="A task is already in progress")
    if not req.accept_tos:
        raise HTTPException(status_code=400, detail="accept_tos is required")
    await runner.start_discover(headless=req.headless, channel=req.channel)

    async def _watch() -> None:
        try:
            if runner._task:
                await runner._task
        except Exception:
            pass
        await _broadcast(_status_payload())

    asyncio.create_task(_watch())
    return {"ok": True, "message": "Discovery started"}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws_clients.append(websocket)
    _ensure_runner_hooks()
    await websocket.send_json(_status_payload())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
