"""FastAPI local dashboard for Webbot."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from webbot import __version__
from webbot.json_scenario import (
    build_step_plan,
    collect_group_plan_labels,
    document_has_explicit_open_url,
    step_label,
)
from webbot.models import (
    FlowGroup,
    GroupsDocument,
    GroupsResponse,
    PythonScenarioSave,
    PythonScenarioSource,
    RunGroupRequest,
    RunRequest,
    RunStatusResponse,
    ScenarioDocument,
    ScenarioInfo,
    ScenarioPreview,
    ScenarioStepPlan,
    ScenarioStepPlanItem,
    StepProgressItem,
)
from webbot.scenario_preview import get_scenario_preview
from webbot.nodriver_browser import nodriver_available
from webbot.runner import RunConfig, RunState, get_runner
from webbot.scenario_store import (
    build_groups_response,
    delete_json_scenario,
    delete_python_scenario,
    finalize_scenario_rename,
    get_group_by_id,
    list_all_scenario_names,
    load_json_scenario,
    load_python_source,
    remove_scenario_from_all_groups,
    save_groups_document,
    save_json_scenario,
    save_python_source,
    scenario_kind,
)
from webbot.scenarios import get_scenario, list_scenario_info

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


def _validate_groups_document(doc: GroupsDocument) -> GroupsDocument:
    known = set(list_all_scenario_names())
    seen_ids: set[str] = set()
    groups: list[FlowGroup] = []
    for g in doc.groups:
        gid = g.id.strip()
        if not gid:
            raise HTTPException(status_code=400, detail="Each group must have a non-empty id")
        if gid in seen_ids:
            raise HTTPException(status_code=400, detail=f"Duplicate group id: {gid}")
        seen_ids.add(gid)
        names: list[str] = []
        for sn in g.scenario_names:
            s = sn.strip()
            if not s:
                continue
            if s not in known:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown scenario '{s}' in group '{gid}'",
                )
            names.append(s)
        groups.append(FlowGroup(id=gid, label=g.label.strip() or gid, scenario_names=names))
    return GroupsDocument(groups=groups)


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


@app.get("/api/groups", response_model=GroupsResponse)
def api_get_groups() -> GroupsResponse:
    return build_groups_response()


@app.put("/api/groups", response_model=GroupsResponse)
def api_put_groups(doc: GroupsDocument) -> GroupsResponse:
    normalized = _validate_groups_document(doc)
    save_groups_document(normalized)
    return build_groups_response()


@app.get("/api/groups/{group_id}/plan", response_model=ScenarioStepPlan)
def api_group_plan(group_id: str) -> ScenarioStepPlan:
    try:
        group = get_group_by_id(group_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    names = [n.strip() for n in group.scenario_names if n.strip()]
    if not names:
        raise HTTPException(status_code=400, detail="Group has no flows")
    labels = collect_group_plan_labels(group.label, names)
    return ScenarioStepPlan(
        name=f"group:{group_id}",
        steps=[ScenarioStepPlanItem(index=i + 1, label=lab) for i, lab in enumerate(labels)],
    )


@app.get("/api/scenarios/{name}/preview", response_model=ScenarioPreview)
def api_scenario_preview(name: str) -> ScenarioPreview:
    try:
        return get_scenario_preview(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/scenarios/{name}/plan", response_model=ScenarioStepPlan)
def api_scenario_plan(name: str, expand: bool = True) -> ScenarioStepPlan:
    try:
        kind = scenario_kind(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if kind is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {name}")

    if kind == "python":
        preview = get_scenario_preview(name)
        pairs = [(s.index, s.label) for s in preview.steps]
        return ScenarioStepPlan(
            name=name,
            steps=[ScenarioStepPlanItem(index=i, label=lab) for i, lab in pairs],
        )

    doc = load_json_scenario(name)
    if expand:
        pairs = build_step_plan(doc, root_name=name)
    else:
        items_flat: list[tuple[int, str]] = []
        offset = 0
        if doc.start_url and not document_has_explicit_open_url(doc.steps):
            items_flat.append((1, f"open URL {doc.start_url}"))
            offset = 1

        for i, step in enumerate(doc.steps, start=1):
            items_flat.append((i + offset, step_label(step)))
        pairs = items_flat
    return ScenarioStepPlan(
        name=name,
        steps=[ScenarioStepPlanItem(index=i, label=lab) for i, lab in pairs],
    )


@app.get("/api/scenarios/{name}/python-source", response_model=PythonScenarioSource)
def api_get_python_source(name: str) -> PythonScenarioSource:
    try:
        kind = scenario_kind(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if kind != "python":
        raise HTTPException(status_code=404, detail="Not a Python scenario")
    try:
        src = load_python_source(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    preview = get_scenario_preview(name)
    desc = preview.description if preview.type == "python" else ""
    return PythonScenarioSource(name=name, source=src, description=desc)


@app.put("/api/scenarios/{name}/python-source", response_model=PythonScenarioSource)
def api_put_python_source(
    name: str,
    body: PythonScenarioSave,
    x_rename_from: str | None = Header(default=None, alias="X-Rename-From"),
) -> PythonScenarioSource:
    stem = name.strip()
    if not stem:
        raise HTTPException(status_code=400, detail="Scenario name is required")
    try:
        save_python_source(stem, body.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SyntaxError as exc:
        raise HTTPException(status_code=400, detail=f"Syntax error: {exc}") from exc
    finalize_scenario_rename(x_rename_from, stem, "python")
    preview = get_scenario_preview(stem)
    desc = preview.description if preview.type == "python" else ""
    return PythonScenarioSource(name=stem, source=load_python_source(stem), description=desc)


@app.get("/api/scenarios/{name}", response_model=ScenarioDocument)
def api_get_scenario(name: str) -> ScenarioDocument:
    try:
        return load_json_scenario(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/scenarios", response_model=ScenarioDocument)
def api_save_scenario(
    doc: ScenarioDocument,
    x_rename_from: str | None = Header(default=None, alias="X-Rename-From"),
) -> ScenarioDocument:
    if not doc.name.strip():
        raise HTTPException(status_code=400, detail="Scenario name is required")
    try:
        save_json_scenario(doc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finalize_scenario_rename(x_rename_from, doc.name, "json")
    return doc


@app.delete("/api/scenarios/{name}")
def api_delete_scenario(name: str) -> dict:
    try:
        kind = scenario_kind(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if kind is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {name}")
    try:
        if kind == "json":
            delete_json_scenario(name)
        else:
            delete_python_scenario(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    remove_scenario_from_all_groups(name)
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


@app.post("/api/run/group")
async def api_start_run_group(req: RunGroupRequest) -> dict:
    _ensure_runner_hooks()
    runner = get_runner()
    if runner.status.state == RunState.running:
        raise HTTPException(status_code=409, detail="A run is already in progress")

    if req.loops < 1:
        raise HTTPException(status_code=400, detail="loops must be at least 1")

    from webbot.scenario_store import get_group_by_id

    try:
        group = get_group_by_id(req.group_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    names = [n.strip() for n in group.scenario_names if n.strip()]
    if not names:
        raise HTTPException(status_code=400, detail="Group has no flows")

    config = RunConfig(
        group_id=req.group_id,
        loops=req.loops,
        pause_between_loops_sec=req.pause_between_loops_sec,
        pause_between_flows_sec=req.pause_between_flows_sec,
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

    return {"ok": True, "message": "Group run started"}


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
