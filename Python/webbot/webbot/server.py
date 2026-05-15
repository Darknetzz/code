"""FastAPI local dashboard for Webbot."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from webbot import __version__
from webbot.models import (
    RunRequest,
    RunStatusResponse,
    ScenarioDocument,
    ScenarioInfo,
    ScenarioPreview,
    StepProgressItem,
)
from webbot.scenario_preview import get_scenario_preview
from webbot.nodriver_browser import nodriver_available
from webbot.runner import RunConfig, RunState, get_runner
from webbot.scenario_store import delete_json_scenario, load_json_scenario, save_json_scenario
from webbot.scenarios import list_scenario_info, scenario_type

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Webbot", description="Human-like browser automation dashboard")

_ws_clients: list[WebSocket] = []


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
    st = get_runner().status
    return {
        "type": "status",
        "state": st.state.value,
        "scenario": st.scenario,
        "loop": st.loop,
        "loops": st.loops,
        "step": st.step,
        "steps": st.steps,
        "step_label": st.step_label,
        "error": st.error,
        "step_progress": st.step_progress,
    }


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


@app.get("/api/health")
def health() -> dict:
    try:
        import playwright  # noqa: F401

        pw = True
    except ImportError:
        pw = False
    return {
        "version": __version__,
        "playwright": pw,
        "nodriver": nodriver_available(),
    }


@app.get("/api/scenarios", response_model=list[ScenarioInfo])
def api_list_scenarios() -> list[ScenarioInfo]:
    return list_scenario_info()


@app.get("/api/scenarios/{name}/preview", response_model=ScenarioPreview)
def api_scenario_preview(name: str) -> ScenarioPreview:
    try:
        return get_scenario_preview(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/scenarios/{name}", response_model=ScenarioDocument)
def api_get_scenario(name: str) -> ScenarioDocument:
    if scenario_type(name) != "json":
        raise HTTPException(status_code=404, detail="Only JSON scenarios can be loaded for editing")
    try:
        return load_json_scenario(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/scenarios", response_model=ScenarioDocument)
def api_save_scenario(doc: ScenarioDocument) -> ScenarioDocument:
    if not doc.name.strip():
        raise HTTPException(status_code=400, detail="Scenario name is required")
    save_json_scenario(doc)
    return doc


@app.delete("/api/scenarios/{name}")
def api_delete_scenario(name: str) -> dict:
    try:
        if scenario_type(name) == "python":
            raise HTTPException(status_code=400, detail="Cannot delete built-in Python scenarios")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {name}") from exc
    try:
        delete_json_scenario(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/run/status", response_model=RunStatusResponse)
def api_run_status() -> RunStatusResponse:
    st = get_runner().status
    return RunStatusResponse(
        state=st.state.value,
        scenario=st.scenario,
        loop=st.loop,
        loops=st.loops,
        step=st.step,
        steps=st.steps,
        step_label=st.step_label,
        error=st.error,
        step_progress=[StepProgressItem.model_validate(item) for item in st.step_progress],
    )


@app.post("/api/run")
async def api_start_run(req: RunRequest) -> dict:
    _ensure_runner_hooks()
    runner = get_runner()
    if runner.status.state == RunState.running:
        raise HTTPException(status_code=409, detail="A run is already in progress")

    if req.loops < 1:
        raise HTTPException(status_code=400, detail="loops must be at least 1")

    from webbot.scenarios import get_scenario

    try:
        get_scenario(req.scenario)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    config = RunConfig(
        scenario=req.scenario,
        loops=req.loops,
        pause_between_loops_sec=req.pause_between_loops_sec,
        headless=req.headless,
        channel=req.channel,
        slow_mo=req.slow_mo,
    )

    async def _watch_run() -> None:
        try:
            if runner._task:
                await runner._task
        except Exception:
            pass
        await _broadcast(_status_payload())

    await runner.start(config)
    asyncio.create_task(_watch_run())

    return {"ok": True, "message": "Run started"}


@app.post("/api/run/stop")
async def api_stop_run() -> dict:
    await get_runner().stop()
    await _broadcast(_status_payload())
    return {"ok": True}


@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws_clients.append(websocket)
    _ensure_runner_hooks()
    st = get_runner().status
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
