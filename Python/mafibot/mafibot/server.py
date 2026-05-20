"""FastAPI local dashboard for Mafibot."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from mafibot import __version__
from mafibot.brain import get_dry_run_decisions, get_last_idle_detail
from mafibot.preflight import parse_error_playbook, run_preflight_checks
from mafibot.config import BotProfile, get_config_dir, get_profile_dir, get_profiles_dir
from mafibot.config_store import (
    clear_credentials,
    create_profile,
    delete_profile,
    get_credentials_status,
    list_profiles_meta,
    load_profile_document,
    rename_profile,
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
    LogAppendRequest,
    LogLinesResponse,
    LoginRequest,
    PreflightResponse,
    PreflightCheckResponse,
    ProfileCreateRequest,
    ProfileListItem,
    ProfileRenameRequest,
    RunRequest,
    RunStatusResponse,
    SessionMetricsResponse,
    SessionStatusResponse,
)
from mafibot.runner import MafibotRunner, get_runner, run_state_blocks_start
from mafibot.session_log import (
    append_ui_log_line,
    clear_session_log,
    configure_session_file_logging,
    get_log_path,
    open_log_in_default_app,
    read_recent_log_lines,
)
from mafibot.session_metrics import (
    SessionMetrics,
    current_session_metrics,
    load_last_session_summary,
    load_session_history,
)

_STATIC_DIR = Path(__file__).parent / "static"
_ws_clients: list[WebSocket] = []
_runner_hooked = False


def _ui_token_expected() -> str:
    return os.getenv("MAFIBOT_UI_TOKEN", "").strip()


def _check_ui_token(request: Request) -> None:
    expected = _ui_token_expected()
    if not expected:
        return
    token = request.headers.get("X-Mafibot-Token", "").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Mafibot-Token")


@asynccontextmanager
async def _lifespan(application: FastAPI):
    configure_session_file_logging()
    _ensure_runner_hooks()
    yield


app = FastAPI(
    title="Mafibot",
    description="Mafiaspillet autopilot dashboard",
    lifespan=_lifespan,
)


@app.middleware("http")
async def ui_token_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        expected = _ui_token_expected()
        if expected:
            token = request.headers.get("X-Mafibot-Token", "").strip()
            if token != expected:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing X-Mafibot-Token"},
                )
    return await call_next(request)


def _status_response(runner: MafibotRunner) -> RunStatusResponse:
    st = runner.status
    idle = get_last_idle_detail()
    if idle is None and st.last_message and st.last_message.startswith("nothing ready"):
        idle = st.last_message
    live_metrics = current_session_metrics()
    session_metrics = (
        _metrics_to_response(live_metrics) if live_metrics is not None else None
    )
    playbook = parse_error_playbook(st.parse_error) if st.parse_error else None
    return RunStatusResponse(
        state=st.state.value,
        profile=st.profile,
        dry_run=st.dry_run,
        elapsed_sec=st.elapsed_sec(),
        last_action=st.last_action,
        last_message=st.last_message,
        last_reason=st.last_reason,
        idle_detail=idle,
        parse_error=st.parse_error,
        parse_playbook=playbook or None,
        error=st.error,
        game=GameStateResponse(**st.game.__dict__),
        dry_run_decisions=get_dry_run_decisions() if st.dry_run else [],
        session_metrics=session_metrics,
    )


async def _broadcast(message: dict) -> None:
    payload = json.dumps(message)
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            log_debug = __import__("logging").getLogger("mafibot.server")
            log_debug.debug("websocket send failed", exc_info=True)
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


def _ensure_runner_hooks() -> None:
    global _runner_hooked
    if not _runner_hooked:
        runner = get_runner()
        runner.add_log_handler(_runner_log_handler)
        runner.add_status_handler(_runner_status_handler)
        _runner_hooked = True


@app.get("/api/logs", response_model=LogLinesResponse)
def api_get_logs(limit: int = 400) -> LogLinesResponse:
    capped = max(1, min(limit, 2000))
    return LogLinesResponse(
        path=str(get_log_path()),
        lines=read_recent_log_lines(limit=capped),
    )


@app.post("/api/logs")
def api_append_log(req: LogAppendRequest) -> dict:
    append_ui_log_line(req.message)
    return {"ok": True}


@app.delete("/api/logs")
def api_clear_logs() -> dict:
    clear_session_log()
    return {"ok": True}


@app.post("/api/logs/open")
def api_open_log_file() -> dict:
    path = open_log_in_default_app()
    return {"ok": True, "path": str(path)}


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


@app.get("/api/preflight", response_model=PreflightResponse)
def api_preflight(require_verification: bool = False) -> PreflightResponse:
    result = run_preflight_checks(require_verification=require_verification)
    return PreflightResponse(
        ok=result.ok,
        checks=[
            PreflightCheckResponse(
                id=c.id, ok=c.ok, message=c.message, hint=c.hint
            )
            for c in result.checks
        ],
        warnings=result.warnings,
        verification=result.to_dict().get("verification"),
    )


def _metrics_to_response(raw: SessionMetrics) -> SessionMetricsResponse:
    return SessionMetricsResponse.model_validate(raw.to_dict())


@app.get("/api/session/metrics/history", response_model=list[SessionMetricsResponse])
def api_session_metrics_history(limit: int = 30) -> list[SessionMetricsResponse]:
    capped = max(1, min(limit, 200))
    return [_metrics_to_response(raw) for raw in load_session_history(limit=capped)]


@app.get("/api/session/metrics", response_model=SessionMetricsResponse | None)
def api_session_metrics() -> SessionMetricsResponse | None:
    raw = load_last_session_summary()
    if raw is None:
        return None
    return _metrics_to_response(raw)


@app.get("/api/profiles/schema")
def api_profile_schema() -> dict:
    return BotProfile.model_json_schema()


@app.get("/api/profiles", response_model=list[ProfileListItem])
def api_list_profiles() -> list[ProfileListItem]:
    return list_profiles_meta()


@app.post("/api/profiles", response_model=BotProfileDocument)
def api_create_profile(req: ProfileCreateRequest) -> BotProfileDocument:
    try:
        return create_profile(req.name, copy_from=req.copy_from)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@app.post("/api/profiles/{name}/rename", response_model=BotProfileDocument)
def api_rename_profile(name: str, req: ProfileRenameRequest) -> BotProfileDocument:
    try:
        return rename_profile(name, req.new_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/profiles/{name}")
def api_delete_profile(name: str) -> dict:
    try:
        delete_profile(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": f"Deleted profile {name}"}


@app.get("/api/credentials", response_model=CredentialsStatus)
def api_get_credentials() -> CredentialsStatus:
    return get_credentials_status()


@app.put("/api/credentials", response_model=CredentialsStatus)
def api_put_credentials(body: CredentialsUpdate) -> CredentialsStatus:
    return save_credentials(body)


@app.delete("/api/credentials", response_model=CredentialsStatus)
def api_delete_credentials() -> CredentialsStatus:
    return clear_credentials()


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
            skip_preflight=req.skip_preflight,
            require_verification=req.require_verification,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def _watch() -> None:
        try:
            if runner._task:
                await runner._task
        except Exception:
            __import__("logging").getLogger("mafibot.server").debug(
                "run watch task failed", exc_info=True
            )
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
    await runner.start_discover(
        headless=req.headless,
        channel=req.channel,
        compare_last=req.compare_last,
    )

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
    expected = _ui_token_expected()
    if expected:
        token = websocket.query_params.get("token", "").strip()
        if token != expected:
            await websocket.close(code=4401)
            return
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
