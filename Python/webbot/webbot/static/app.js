const $ = (id) => document.getElementById(id);

/** Client-only id for an unsaved flow row in the list. */
const DRAFT_SCENARIO_ID = "__draft__";

let scenarios = [];
/** @type {{ groups: Array<{id:string,label:string,scenario_names:string[]}>, ungrouped: string[] }} */
let groupsData = { groups: [], ungrouped: [] };
let selectedScenario = null;
let builderSteps = [];
let ws = null;
let runStepProgress = null;
let runShowStepProgress = false;
let cachedPreviewDoc = null;
let cachedScenarioPreview = null;
let runStatusPollTimer = null;

/** True while editing an unsaved Python draft from New flow → Python. */
let draftIsPython = false;

const PYTHON_FLOW_TEMPLATE = `"""Edit this Python flow — saved as a .py file next to JSON scenarios."""

from playwright.async_api import Page

DESCRIPTION = "My Python flow"
STEP_LABELS = ("Open example.com",)


async def run(page: Page) -> None:
    await page.goto("https://example.com", wait_until="domcontentloaded")
`;

/** CodeMirror instance for the Python scenario editor (null if library missing). */
let pythonCodeMirror = null;

function getPythonSource() {
  if (pythonCodeMirror) return pythonCodeMirror.getValue();
  return $("python-source-editor")?.value ?? "";
}

function setPythonSource(text) {
  const v = text ?? "";
  if (pythonCodeMirror) {
    if (pythonCodeMirror.getValue() !== v) pythonCodeMirror.setValue(v);
  } else if ($("python-source-editor")) {
    $("python-source-editor").value = v;
  }
}

function refreshPythonEditorLayout() {
  if (!pythonCodeMirror) return;
  requestAnimationFrame(() => pythonCodeMirror.refresh());
}

function initPythonCodeMirror() {
  const ta = $("python-source-editor");
  // global CodeMirror from CDN (codemirror package)
  if (!ta || pythonCodeMirror || typeof CodeMirror === "undefined") return;
  pythonCodeMirror = CodeMirror.fromTextArea(ta, {
    mode: {
      name: "python",
      version: 3,
      singleLineStringErrors: false,
    },
    theme: "dracula",
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: false,
    matchBrackets: true,
    viewportMargin: 80,
    extraKeys: {
      Tab: (cm) => cm.replaceSelection("    ", "end"),
      "Shift-Tab": "indentLess",
    },
  });
}

function isDraftSelected() {
  return selectedScenario === DRAFT_SCENARIO_ID;
}

function getSelectedScenario() {
  if (isDraftSelected()) return null;
  return selectedScenario || scenarios[0]?.name || null;
}

function getDraftListEntry() {
  const name = $("build-name")?.value.trim();
  const desc = $("build-desc")?.value.trim();
  return {
    name: DRAFT_SCENARIO_ID,
    type: "draft",
    isPython: draftIsPython,
    displayName: name || (draftIsPython ? "Untitled Python draft" : "Untitled draft"),
    description: draftIsPython ? "Unsaved Python flow" : desc || "Unsaved JSON flow",
  };
}

function getScenarioInfo(name) {
  if (name === DRAFT_SCENARIO_ID) return isDraftSelected() ? getDraftListEntry() : null;
  return scenarios.find((s) => s.name === name) || null;
}

function syncDraftListLabel() {
  if (!isDraftSelected()) return;
  const entry = getDraftListEntry();
  const btn = document.querySelector(`.scenario-item[data-name="${DRAFT_SCENARIO_ID}"]`);
  if (!btn) return;
  const nameText = btn.querySelector(".scenario-item-name-text");
  const descEl = btn.querySelector(".scenario-item-desc");
  if (nameText) nameText.textContent = entry.displayName;
  if (descEl) descEl.textContent = entry.description;
  else if (entry.description) {
    const span = document.createElement("span");
    span.className = "scenario-item-desc";
    span.textContent = entry.description;
    btn.appendChild(span);
  }
}

function scenarioListOnSelect(name) {
  selectScenario(name);
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function stepPreviewLabel(step) {
  if (!step?.action) return "step";
  switch (step.action) {
    case "goto":
      return `goto ${step.url || "?"}`;
    case "delay":
      return `delay ${step.min ?? "?"}–${step.max ?? "?"}s`;
    case "scroll":
      return `scroll dy=${step.delta_y ?? "auto"}`;
    case "fill":
      return `fill ${step.selector || step.label || step.name || "?"} = ${JSON.stringify(step.value ?? "")}`;
    case "click":
      return `click ${step.by || "?"} ${step.role || step.text || step.selector || step.data_value || step.test_id || ""}`.trim();
    case "submit_form":
      return `submit_form (${(step.method || "post").toUpperCase()}) ${(step.fields || []).length} field(s)`;
    case "run_scenario":
      return `run scenario: ${step.scenario || "?"}`;
    default:
      return step.action;
  }
}

function stepProgressMarker(status) {
  switch (status) {
    case "running":
      return "…";
    case "ok":
      return "✓";
    case "failed":
      return "✗";
    default:
      return "○";
  }
}

function renderRunStepProgressHtml(steps, loopInfo) {
  const loopHdr =
    loopInfo && loopInfo.loops > 1
      ? `<p class="run-step-loop muted">Loop ${loopInfo.loop}/${loopInfo.loops}</p>`
      : "";
  const items = steps
    .map((s) => {
      const err = s.error
        ? `<span class="run-step-error">${escapeHtml(s.error)}</span>`
        : "";
      return `<li class="run-step run-step-${s.status}" data-index="${s.index}">
        <span class="run-step-marker" aria-hidden="true">${stepProgressMarker(s.status)}</span>
        <span class="run-step-num">${s.index}.</span>
        <span class="run-step-label">${escapeHtml(s.label)}</span>${err}
      </li>`;
    })
    .join("");
  return `${loopHdr}<ol class="run-step-progress">${items}</ol>`;
}

function renderRunProgressPanel(loopInfo) {
  const body = $("run-progress-body");
  if (!body || !runStepProgress?.length) return;
  body.innerHTML = renderRunStepProgressHtml(runStepProgress, loopInfo);
}

function setRunProgressVisible(show) {
  $("run-progress-wrap")?.classList.toggle("hidden", !show);
  if (show) {
    $("flow-editor-wrap")?.classList.add("hidden");
    $("flow-python-editor-wrap")?.classList.add("hidden");
  }
}

function restoreEditorViewAfterRun() {
  if (runShowStepProgress) return;
  if (isPythonUi()) showPythonFlowEditor();
  else showJsonFlowEditor();
}

function isPythonUi() {
  if (draftIsPython && isDraftSelected()) return true;
  if (!isDraftSelected() && getScenarioInfo(selectedScenario)?.type === "python") return true;
  return false;
}

function updateFlowNameReadonly() {
  const inp = $("build-name");
  if (!inp) return;
  const locked =
    Boolean(selectedScenario) &&
    selectedScenario !== DRAFT_SCENARIO_ID &&
    getScenarioInfo(selectedScenario)?.type === "python";
  inp.readOnly = locked;
}

function showPythonFlowEditor() {
  if (!runShowStepProgress) $("run-progress-wrap")?.classList.add("hidden");
  $("flow-editor-wrap")?.classList.add("hidden");
  $("flow-python-editor-wrap")?.classList.remove("hidden");
  $("build-msg").textContent = "";
  updateFlowNameReadonly();
  refreshPythonEditorLayout();
}

async function initRunStepProgress(runTarget) {
  runStepProgress = [];
  try {
    if (typeof runTarget === "string" && runTarget.startsWith("group:")) {
      const gid = runTarget.slice("group:".length);
      const plan = await api(`/api/groups/${encodeURIComponent(gid)}/plan`);
      cachedScenarioPreview = null;
      cachedPreviewDoc = null;
      runStepProgress = (plan.steps || []).map((s) => ({
        index: s.index,
        label: s.label,
        status: "pending",
        error: null,
      }));
    } else {
      const preview = await fetchScenarioPreview(runTarget);
      cachedScenarioPreview = preview;
      runStepProgress = stepPlanFromPreview(preview);
      try {
        cachedPreviewDoc = await api(`/api/scenarios/${encodeURIComponent(runTarget)}`);
      } catch {
        cachedPreviewDoc = null;
      }
    }
  } catch {
    runStepProgress = [];
  }
  runShowStepProgress = true;
  setRunProgressVisible(true);
  renderRunProgressPanel();
}

function stopRunStatusPolling() {
  if (runStatusPollTimer != null) {
    clearInterval(runStatusPollTimer);
    runStatusPollTimer = null;
  }
}

function startRunStatusPolling() {
  stopRunStatusPolling();
  runStatusPollTimer = setInterval(() => {
    refreshRunStepProgressFromServer().catch(() => {});
  }, 350);
}

async function refreshRunStepProgressFromServer() {
  const st = await api("/api/run/status");
  setRunStatus(st);
  applyRunStepProgress(st);
  updateRunButtons(st.state);
  if (st.state !== "running") stopRunStatusPolling();
  return st;
}

function upsertRunStepEntry(index, label, status, error = null) {
  if (!runStepProgress) runStepProgress = [];
  let entry = runStepProgress.find((s) => s.index === index);
  if (!entry) {
    entry = { index, label, status, error };
    runStepProgress.push(entry);
    runStepProgress.sort((a, b) => a.index - b.index);
  } else {
    if (label) entry.label = label;
    entry.status = status;
    entry.error = error;
  }
  runShowStepProgress = true;
}

function applyStepProgressFromLogLine(line) {
  if (!runShowStepProgress) return;
  const m = line.match(/\[(?:\.\.|OK|FAIL)\](?:.*?)step (\d+)\/(\d+):\s*(.+?)(?:\s+-\s+(.+))?$/);
  if (!m) return;
  const index = parseInt(m[1], 10);
  const label = m[3].trim();
  const err = m[4]?.trim() || null;
  let status = "running";
  if (line.startsWith("[OK]")) status = "ok";
  else if (line.startsWith("[FAIL]")) status = "failed";

  upsertRunStepEntry(index, label, status, err);
  if (status === "running") {
    runStepProgress.forEach((s) => {
      if (s.index < index && s.status === "running") s.status = "ok";
    });
  }
  renderRunProgressPanel();
}

function applyRunStepProgress(msg) {
  const loopInfo = { loop: msg.loop, loops: msg.loops };

  if (msg.step_progress?.length) {
    runStepProgress = msg.step_progress.map((s) => ({ ...s }));
    runShowStepProgress = true;
    setRunProgressVisible(true);
    renderRunProgressPanel(loopInfo);
    return;
  }

  if (msg.state === "running" && msg.step && msg.step_label) {
    const idx = msg.step;
    upsertRunStepEntry(idx, msg.step_label, "running");
    runStepProgress.forEach((s) => {
      if (s.index < idx && s.status === "running") s.status = "ok";
    });
    setRunProgressVisible(true);
    renderRunProgressPanel(loopInfo);
    return;
  }

  if (
    runStepProgress?.length &&
    (msg.state === "completed" || msg.state === "failed" || msg.state === "stopped")
  ) {
    if (msg.state === "completed") {
      runStepProgress.forEach((s) => {
        s.status = "ok";
        s.error = null;
      });
    } else if (msg.state === "failed" && msg.step) {
      const failAt = msg.step;
      runStepProgress.forEach((s) => {
        if (s.index < failAt) {
          s.status = "ok";
          s.error = null;
        } else if (s.index === failAt) {
          s.status = "failed";
          s.error = msg.error || s.error;
        }
      });
    }
    runShowStepProgress = true;
    setRunProgressVisible(true);
    renderRunProgressPanel(loopInfo);
  }
}

function clearRunStepProgress() {
  runStepProgress = null;
  runShowStepProgress = false;
  stopRunStatusPolling();
  $("run-progress-wrap")?.classList.add("hidden");
  restoreEditorViewAfterRun();
}

async function fetchScenarioPreview(name) {
  return api(`/api/scenarios/${encodeURIComponent(name)}/preview`);
}

function renderScenarioPreviewHtml(preview) {
  const parts = [];
  if (preview.description) parts.push(`<p class="flow-preview-desc">${escapeHtml(preview.description)}</p>`);
  if (preview.source) {
    parts.push(
      `<p class="flow-preview-meta"><strong>Source:</strong> <code>${escapeHtml(preview.source)}</code></p>`
    );
  }
  if (preview.start_url) {
    parts.push(`<p class="flow-preview-meta"><strong>Start URL:</strong> ${escapeHtml(preview.start_url)}</p>`);
  }
  if (preview.random_delay_between_steps) {
    parts.push(
      `<p class="flow-preview-meta"><strong>Between steps:</strong> ${preview.between_steps_min}–${preview.between_steps_max}s (${escapeHtml(preview.between_steps_distribution || "triangular")})</p>`
    );
  }
  const steps = preview.steps || [];
  if (steps.length === 0) {
    parts.push('<p class="muted">No steps defined.</p>');
  } else {
    const items = steps
      .map((s) => `<li>${escapeHtml(typeof s === "string" ? s : s.label)}</li>`)
      .join("");
    parts.push(`<ol class="flow-preview-steps">${items}</ol>`);
  }
  return parts.join("");
}

function stepPlanFromPreview(preview) {
  return (preview.steps || []).map((s) => ({
    index: s.index,
    label: s.label,
    status: "pending",
    error: null,
  }));
}

function showJsonFlowEditor() {
  if (!runShowStepProgress) $("run-progress-wrap")?.classList.add("hidden");
  $("flow-python-editor-wrap")?.classList.add("hidden");
  $("flow-editor-wrap")?.classList.remove("hidden");
  setFlowEditorMode(true);
  $("build-msg-python").textContent = "";
  updateFlowNameReadonly();
}

function setFlowEditorMode(jsonEditable) {
  const wrap = $("flow-editor-wrap");
  if (wrap) {
    wrap.classList.remove("hidden");
    wrap.classList.toggle("flow-editor-readonly", jsonEditable === false);
  }
  const disable = jsonEditable === false;
  wrap?.querySelectorAll("input, select, button").forEach((el) => {
    if (el.id === "btn-save" || el.id === "btn-test-run" || el.id === "btn-add-step") {
      el.disabled = disable;
    } else if (!el.closest(".step-actions")) {
      el.disabled = disable;
    }
  });
}

function updateDeleteFlowButton() {
  const btn = $("btn-delete-flow");
  if (!btn) return;
  const label = btn.querySelector(".btn-label");
  if (isDraftSelected()) {
    btn.disabled = false;
    if (label) label.textContent = "Discard";
    btn.setAttribute("aria-label", "Discard draft");
    return;
  }
  if (label) label.textContent = "Delete";
  btn.setAttribute("aria-label", "Delete");
  btn.disabled = !selectedScenario;
}

function populateFlowEditor(doc) {
  $("build-name").value = doc.name || "";
  $("build-desc").value = doc.description || "";
  $("build-url").value = doc.start_url || "";
  renderScenarioOptions(doc);
  builderSteps = (doc.steps || []).map((s) => normalizeStep({ ...s }));
  renderSteps();
}

function clearFlowEditor() {
  $("build-name").value = "";
  $("build-desc").value = "";
  $("build-url").value = "";
  $("build-random-between-steps").checked = false;
  renderScenarioOptions();
  builderSteps = [defaultStep("goto")];
  renderSteps();
}

function newFlow() {
  draftIsPython = false;
  if (isDraftSelected()) {
    if (!confirm("Discard current draft and start a new one?")) return;
    clearFlowEditor();
    $("build-msg").textContent = "Draft — enter a name and save.";
    syncDraftListLabel();
    return;
  }
  setSelectedScenario(DRAFT_SCENARIO_ID, { skipPreview: true });
  clearFlowEditor();
  showJsonFlowEditor();
  renderScenarioList("scenario-list", scenarioListOnSelect);
  syncScenarioListSelection();
  $("build-msg").textContent = "Draft — enter a name and save.";
  updateDeleteFlowButton();
  clearRunStepProgress();
}

function newPythonFlow() {
  if (isDraftSelected()) {
    if (!confirm("Discard current draft and start a new Python draft?")) return;
    draftIsPython = true;
    clearFlowEditor();
    $("build-name").value = "";
    setPythonSource(PYTHON_FLOW_TEMPLATE);
    $("build-msg-python").textContent = "Draft — enter a name and save.";
    syncDraftListLabel();
    showPythonFlowEditor();
    renderScenarioList("scenario-list", scenarioListOnSelect);
    syncScenarioListSelection();
    updateDeleteFlowButton();
    clearRunStepProgress();
    return;
  }
  draftIsPython = true;
  setSelectedScenario(DRAFT_SCENARIO_ID, { skipPreview: true });
  clearFlowEditor();
  $("build-name").value = "";
  setPythonSource(PYTHON_FLOW_TEMPLATE);
  showPythonFlowEditor();
  renderScenarioList("scenario-list", scenarioListOnSelect);
  syncScenarioListSelection();
  $("build-msg-python").textContent = "Draft — enter a name and save.";
  updateDeleteFlowButton();
  clearRunStepProgress();
}

async function discardDraft() {
  if (!isDraftSelected()) return;
  draftIsPython = false;
  setSelectedScenario(null, { skipPreview: true });
  renderScenarioList("scenario-list", scenarioListOnSelect);
  if (scenarios.length) {
    await selectScenario(scenarios[0].name);
  } else {
    clearFlowEditor();
    showJsonFlowEditor();
    $("build-msg").textContent = "";
    $("build-msg-python").textContent = "";
    updateDeleteFlowButton();
  }
}

async function selectScenario(name) {
  if (name === selectedScenario) return;
  const leavingDraft = isDraftSelected() && name !== DRAFT_SCENARIO_ID;
  if (leavingDraft && !confirm("Discard unsaved draft?")) return;
  if (selectedScenario !== name) clearRunStepProgress();
  setSelectedScenario(name, { skipPreview: true });
  if (leavingDraft) {
    renderScenarioList("scenario-list", scenarioListOnSelect);
    syncScenarioListSelection();
  }
  await loadFlowIntoEditor(name);
}

async function loadFlowIntoEditor(name) {
  $("build-msg").textContent = "";
  $("build-msg-python").textContent = "";
  if (!name) return;

  if (name === DRAFT_SCENARIO_ID) {
    if (draftIsPython) {
      showPythonFlowEditor();
      $("build-msg-python").textContent = "Draft — enter a name and save.";
    } else {
      showJsonFlowEditor();
      $("build-msg").textContent = "Draft — enter a name and save.";
    }
    updateDeleteFlowButton();
    return;
  }

  const info = getScenarioInfo(name);
  if (!info) {
    $("build-msg").textContent = "Flow not found";
    return;
  }

  draftIsPython = false;
  setSelectedScenario(name, { skipPreview: true });

  if (info.type === "python") {
    showPythonFlowEditor();
    $("build-name").value = name;
    try {
      const payload = await api(`/api/scenarios/${encodeURIComponent(name)}/python-source`);
      setPythonSource(payload.source);
      refreshPythonEditorLayout();
      $("build-msg-python").textContent = `Editing "${name}"`;
      updateDeleteFlowButton();
      updateFlowNameReadonly();
    } catch (e) {
      $("build-msg-python").textContent = e.message;
    }
    return;
  }

  showJsonFlowEditor();
  try {
    const doc = await api(`/api/scenarios/${encodeURIComponent(name)}`);
    populateFlowEditor(doc);
    $("build-msg").textContent = `Editing "${name}"`;
    updateDeleteFlowButton();
    updateFlowNameReadonly();
  } catch (e) {
    $("build-msg").textContent = e.message;
  }
}

async function deleteSelectedFlow() {
  if (isDraftSelected()) {
    if (!confirm("Discard unsaved draft?")) return;
    await discardDraft();
    $("build-msg").textContent = "Draft discarded";
    $("build-msg-python").textContent = "";
    return;
  }
  const name = selectedScenario;
  if (!name) return;
  if (!confirm(`Delete flow "${name}"? This cannot be undone.`)) return;
  await api(`/api/scenarios/${encodeURIComponent(name)}`, { method: "DELETE" });
  await loadScenarios();
  if (scenarios.length) await selectScenario(scenarios[0].name);
  else newFlow();
  $("build-msg").textContent = `Deleted "${name}"`;
  $("build-msg-python").textContent = "";
}

function syncScenarioListSelection() {
  document.querySelectorAll(".scenario-item").forEach((btn) => {
    const on = selectedScenario && btn.dataset.name === selectedScenario;
    btn.classList.toggle("selected", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
}

function setSelectedScenario(name, options = {}) {
  const prev = selectedScenario;
  selectedScenario = name || null;
  syncScenarioListSelection();
  updateDeleteFlowButton();
  if (!options.skipPreview && prev !== selectedScenario) clearRunStepProgress();
}

function buildScenarioListItem(s, onSelect) {
  const li = document.createElement("li");
  li.className = "scenario-list-item";

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "scenario-item";
  btn.dataset.name = s.name;
  btn.setAttribute("role", "option");

  const nameEl = document.createElement("span");
  nameEl.className = "scenario-item-name";
  if (typeof icon === "function") nameEl.appendChild(icon("list", "icon icon-scenario"));
  const nameText = document.createElement("span");
  nameText.className = "scenario-item-name-text";
  nameText.textContent = s.displayName ?? s.name;
  nameEl.appendChild(nameText);

  const typeEl = document.createElement("span");
  let typeClass = "scenario-item-type type-json";
  /** @type {"json"|"python"|null} */
  let badgeKind = "json";
  let typeShortLabel = "json";

  if (s.type === "draft") {
    typeClass = "scenario-item-type type-draft";
    badgeKind = s.isPython ? "python" : null;
    typeShortLabel = "draft";
    btn.classList.add("scenario-item-draft");
  } else if (s.type === "python") {
    typeClass = "scenario-item-type type-python";
    badgeKind = "python";
    typeShortLabel = "python";
  }

  typeEl.className = typeClass;
  if (typeof icon === "function" && badgeKind) {
    typeEl.appendChild(icon(badgeKind, "icon icon-badge"));
  }
  const typeLabel = document.createElement("span");
  typeLabel.textContent = typeShortLabel;
  typeEl.appendChild(typeLabel);

  btn.appendChild(nameEl);
  btn.appendChild(typeEl);

  if (s.description) {
    const descEl = document.createElement("span");
    descEl.className = "scenario-item-desc";
    descEl.textContent = s.description;
    btn.appendChild(descEl);
  }

  btn.addEventListener("click", () => onSelect(s.name));
  li.appendChild(btn);

  return li;
}

async function loadGroups() {
  groupsData = await api("/api/groups");
}

function renderScenarioList(containerId, onSelect) {
  const list = $(containerId);
  if (!list) return;
  list.innerHTML = "";

  const draftRows = isDraftSelected() ? [getDraftListEntry()] : [];
  const editableFlows = scenarios.filter((s) => s.type === "json" || s.type === "python");

  const showEmpty =
    draftRows.length === 0 &&
    editableFlows.length === 0 &&
    !(groupsData.groups && groupsData.groups.length);

  if (showEmpty) {
    const empty = document.createElement("li");
    empty.className = "scenario-list-empty";
    empty.textContent = "No flows found";
    list.appendChild(empty);
    return;
  }

  for (const d of draftRows) {
    list.appendChild(buildScenarioListItem(d, onSelect));
  }

  const assigned = new Set();
  for (const g of groupsData.groups || []) {
    const wrap = document.createElement("li");
    wrap.className = "scenario-list-group-wrap";
    const details = document.createElement("details");
    details.className = "scenario-group-details";
    details.open = true;

    const summary = document.createElement("summary");
    summary.className = "scenario-group-summary";

    const lab = document.createElement("span");
    lab.className = "scenario-group-label";
    lab.textContent = g.label || g.id;

    const runGrp = document.createElement("button");
    runGrp.type = "button";
    runGrp.className = "scenario-group-run outline success";
    runGrp.textContent = "Run group";
    runGrp.title = `Run flows in “${g.label || g.id}” in order`;
    runGrp.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      startRunGroup(g.id).catch((err) => {
        $("build-msg").textContent = err.message;
      });
    });

    summary.appendChild(lab);
    summary.appendChild(runGrp);
    details.appendChild(summary);

    const sub = document.createElement("ul");
    sub.className = "scenario-group-flows";
    let anyMember = false;
    for (const nm of g.scenario_names || []) {
      const flow = editableFlows.find((x) => x.name === nm);
      if (!flow) continue;
      anyMember = true;
      assigned.add(nm);
      sub.appendChild(buildScenarioListItem(flow, onSelect));
    }
    if (!anyMember) {
      const hint = document.createElement("li");
      hint.className = "muted scenario-list-empty";
      hint.style.listStyle = "none";
      hint.textContent = "No flows in this group";
      sub.appendChild(hint);
    }
    details.appendChild(sub);
    wrap.appendChild(details);
    list.appendChild(wrap);
  }

  const ungrouped = (groupsData.ungrouped || []).filter((nm) =>
    editableFlows.some((x) => x.name === nm)
  );

  if (ungrouped.length) {
    const ugWrap = document.createElement("li");
    ugWrap.className = "scenario-list-group-wrap";
    const h = document.createElement("div");
    h.className = "scenario-ungrouped-heading muted field-label";
    h.textContent = "Ungrouped";
    ugWrap.appendChild(h);
    const ul = document.createElement("ul");
    ul.className = "scenario-group-flows";
    for (const nm of ungrouped) {
      const flow = editableFlows.find((x) => x.name === nm);
      if (!flow) continue;
      ul.appendChild(buildScenarioListItem(flow, onSelect));
    }
    ugWrap.appendChild(ul);
    list.appendChild(ugWrap);
  }

  syncScenarioListSelection();
}

function appendLog(line) {
  const el = $("log-output");
  el.textContent += line + "\n";
  el.scrollTop = el.scrollHeight;
  applyStepProgressFromLogLine(line);
}

function formatRunDetail(msg) {
  const parts = [];
  if (msg.loops > 1 && msg.loop) {
    parts.push(`loop ${msg.loop}/${msg.loops}`);
  }
  if (msg.state === "running" && msg.step && msg.steps) {
    parts.push(`step ${msg.step}/${msg.steps}`);
    if (msg.step_label) parts.push(msg.step_label);
  } else if (msg.state === "completed" && msg.steps) {
    parts.push(`${msg.steps} step(s) verified`);
  }
  return parts.join(" · ");
}

function setRunStatus(msg) {
  const state = typeof msg === "string" ? msg : msg.state;
  const el = $("run-status");
  el.className = "status " + (state || "muted");
  const labels = {
    idle: "Idle",
    running: "Running…",
    completed: "Completed",
    failed: "Failed",
    stopped: "Stopped",
  };
  const detail = typeof msg === "object" ? formatRunDetail(msg) : "";
  el.textContent = (labels[state] || state) + (detail ? ` — ${detail}` : "");
}

function updateRunButtons(state) {
  const running = state === "running";
  $("btn-start").disabled = running || !getSelectedScenario();
  $("btn-stop").disabled = !running;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function loadHealth() {
  const h = await api("/api/health");
  $("health").textContent = `v${h.version} · Playwright ${h.playwright ? "ok" : "missing"}`;
}

async function loadScenarios() {
  scenarios = await api("/api/scenarios");
  await loadGroups();

  if (scenarios.length === 0 && !isDraftSelected()) {
    selectedScenario = null;
    renderScenarioList("scenario-list", scenarioListOnSelect);
    clearRunStepProgress();
    updateDeleteFlowButton();
    return;
  }

  const stillValid =
    isDraftSelected() ||
    (selectedScenario && scenarios.some((s) => s.name === selectedScenario));
  if (!stillValid) selectedScenario = scenarios[0]?.name ?? null;

  renderScenarioList("scenario-list", scenarioListOnSelect);
  if (selectedScenario) await selectScenario(selectedScenario);
}

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws/logs`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "log") appendLog(msg.message);
    if (msg.type === "status") {
      setRunStatus(msg);
      applyRunStepProgress(msg);
      if (msg.error) appendLog("Error: " + msg.error);
      updateRunButtons(msg.state);
      if (msg.state === "completed" || msg.state === "failed" || msg.state === "stopped") {
        stopRunStatusPolling();
        refreshRunStepProgressFromServer().catch(() => {});
      }
    }
  };
  ws.onclose = () => setTimeout(connectWebSocket, 2000);
}

const STEP_TYPES = ["goto", "click", "fill", "submit_form", "delay", "scroll", "run_scenario"];

function changeStepType(index, newAction) {
  if (builderSteps[index].action === newAction) return;
  builderSteps[index] = defaultStep(newAction);
  renderSteps();
}

function defaultStep(action) {
  switch (action) {
    case "goto":
      return { action: "goto", url: $("build-url").value || "https://example.com" };
    case "click":
      return { action: "click", by: "role", role: "button", name: "" };
    case "delay":
      return {
        action: "delay",
        min: 0.5,
        max: 1.2,
        distribution: "triangular",
        long_pause_chance: 0.08,
        long_pause_min: 2,
        long_pause_max: 5,
      };
    case "scroll":
      return {
        action: "scroll",
        delta_y: 300,
        steps_min: 4,
        steps_max: 9,
        step_delay_min: 0.06,
        step_delay_max: 0.35,
        overscroll: true,
        overscroll_ratio_min: 0.06,
        overscroll_ratio_max: 0.14,
        pause_after_min: 0.25,
        pause_after_max: 0.9,
        variable_step_size: true,
      };
    case "fill":
      return { action: "fill", by: "css", selector: "", value: "" };
    case "submit_form":
      return {
        action: "submit_form",
        method: "post",
        form_selector: "",
        fields: [],
        submit_by: "role",
        submit_role: "button",
        submit_name: "Submit",
        wait_for_navigation: true,
      };
    case "run_scenario":
      return {
        action: "run_scenario",
        scenario: "",
        inherit_delays: false,
        skip_start_url: true,
      };
    default:
      return { action };
  }
}

const LOCATOR_BY_OPTIONS = ["role", "text", "css", "data", "label"];

/** Map legacy test_id locators to the data-attribute editor. */
function normalizeLocatorFields(obj) {
  if (!obj || obj.by !== "test_id") return obj;
  return {
    ...obj,
    by: "data",
    data_attr: obj.data_attr || "data-testid",
    data_value: obj.data_value ?? obj.test_id ?? "",
  };
}

function normalizeStep(step) {
  if (!step) return step;
  const s = normalizeLocatorFields({ ...step });
  if (s.action === "submit_form" && Array.isArray(s.fields)) {
    s.fields = s.fields.map((f) => normalizeLocatorFields({ ...f }));
  }
  if (s.action === "run_scenario") {
    s.inherit_delays = !!s.inherit_delays;
    s.skip_start_url = s.skip_start_url !== false;
    if (typeof s.scenario !== "string") s.scenario = "";
  }
  return s;
}

/** [fieldKey, label, inputType, hint, helpId] for each Find-by mode */
function locatorFieldDefs(by) {
  switch (by) {
    case "role":
      return [
        ["role", "Role", "text", "e.g. button, link, textbox", "locator.role"],
        ["name", "Accessible name", "text", "Visible or aria-label text", "locator.name"],
      ];
    case "text":
      return [["text", "Visible text", "text", "Text shown on the page", "locator.text"]];
    case "css":
      return [
        ["selector", "CSS selector", "text", "e.g. #id, .class, button.submit", "locator.selector"],
      ];
    case "data":
      return [
        [
          "data_attr",
          "Data attribute",
          "text",
          "e.g. data-testid, data-cy, data-qa",
          "locator.data_attr",
        ],
        ["data_value", "Attribute value", "text", "Value on that attribute", "locator.data_value"],
      ];
    case "label":
      return [["label", "Label text", "text", "Text on the associated <label>", "locator.label"]];
    default:
      return [];
  }
}

function renderLocatorInputs(container, step, includeValue) {
  const loc = normalizeLocatorFields(step);
  const by = loc.by || "css";
  for (const [field, label, type, hint, helpId] of locatorFieldDefs(by)) {
    container.appendChild(labeledField(field, label, loc[field] || "", type, hint, helpId));
  }
  if (includeValue) {
    container.appendChild(
      labeledField(
        "value",
        "Value to type",
        loc.value || "",
        "text",
        "Text entered into the field",
        "locator.value"
      )
    );
  }
}

function appendLocatorFields(container, step, includeValue, stepIndex) {
  const loc = normalizeLocatorFields(step);
  const byWrap = labeledSelect(
    "by",
    "Find by",
    loc.by || "css",
    LOCATOR_BY_OPTIONS,
    "",
    "locator.by"
  );
  byWrap.querySelector("select").addEventListener("change", (e) => {
    const row = document.querySelector(`[data-step-index="${stepIndex}"]`);
    if (row) syncStepFromDom(stepIndex, row);
    builderSteps[stepIndex].by = e.target.value;
    renderSteps();
  });
  container.appendChild(byWrap);
  renderLocatorInputs(container, loc, includeValue);
}

function renderFormFieldRow(stepIndex, fieldIndex, field) {
  const wrap = document.createElement("div");
  wrap.className = "form-field-row";

  const locGrid = document.createElement("div");
  locGrid.className = "form-field-row-inputs";

  const addCol = (labelText, el, parent, helpId = null) => {
    const col = document.createElement("div");
    col.className = "field-labeled";
    const labRow = document.createElement("div");
    labRow.className = "label-row";
    const lab = document.createElement("span");
    lab.className = "field-label";
    lab.textContent = labelText;
    labRow.appendChild(lab);
    col.appendChild(labRow);
    col.appendChild(el);
    parent.appendChild(col);
  };

  const renderFieldInputs = () => {
    locGrid.innerHTML = "";
    const normalized = normalizeLocatorFields(field);
    Object.assign(field, normalized);
    const by = field.by || "css";

    const bySel = fieldSelect("by", by, LOCATOR_BY_OPTIONS);
    bySel.addEventListener("change", () => {
      field.by = bySel.value;
      renderFieldInputs();
    });
    addCol("Find by", bySel, locGrid, "locator.by");

    for (const [key, label, type, , helpId] of locatorFieldDefs(by)) {
      const inp = fieldInput(key, field[key] || "", type);
      inp.addEventListener("input", () => {
        field[key] = inp.value;
      });
      addCol(label, inp, locGrid, helpId);
    }

    const valueInp = fieldInput("value", field.value || "");
    valueInp.addEventListener("input", () => {
      field.value = valueInp.value;
    });
    addCol("Value", valueInp, locGrid, "locator.value");
  };

  renderFieldInputs();
  wrap.appendChild(locGrid);

  const del =
    typeof makeIconButton === "function"
      ? makeIconButton(
          "trash",
          "Remove field",
          (e) => {
            e.stopPropagation();
            builderSteps[stepIndex].fields.splice(fieldIndex, 1);
            renderSteps();
          },
          { danger: true }
        )
      : (() => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "danger";
          b.textContent = "×";
          b.title = "Remove field";
          b.onclick = (e) => {
            e.stopPropagation();
            builderSteps[stepIndex].fields.splice(fieldIndex, 1);
            renderSteps();
          };
          return b;
        })();
  del.classList.add("btn-remove-field");
  wrap.appendChild(del);
  return wrap;
}

let stepDragFromIndex = null;

function reorderStep(from, to) {
  if (from === to || from < 0 || to < 0 || from >= builderSteps.length || to >= builderSteps.length) {
    return;
  }
  const [item] = builderSteps.splice(from, 1);
  builderSteps.splice(to, 0, item);
  renderSteps();
}

function clearStepDropIndicators() {
  document.querySelectorAll(".step-row").forEach((row) => {
    row.classList.remove("step-drop-before", "step-dragging");
  });
}

function initStepDragDrop(list) {
  if (!list || list.closest(".flow-editor-readonly")) return;

  list.querySelectorAll(".step-row").forEach((row) => {
    const handle = row.querySelector(".step-drag-handle");
    if (!handle) return;

    const rowIndex = () => parseInt(row.dataset.stepIndex, 10);

    handle.addEventListener("dragstart", (e) => {
      stepDragFromIndex = rowIndex();
      row.classList.add("step-dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(stepDragFromIndex));
      if (e.dataTransfer.setDragImage) {
        e.dataTransfer.setDragImage(row, 20, 20);
      }
    });

    handle.addEventListener("dragend", () => {
      stepDragFromIndex = null;
      clearStepDropIndicators();
    });

    row.addEventListener("dragover", (e) => {
      if (stepDragFromIndex === null) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      if (rowIndex() === stepDragFromIndex) return;
      list.querySelectorAll(".step-row").forEach((r) => r.classList.remove("step-drop-before"));
      row.classList.add("step-drop-before");
    });

    row.addEventListener("dragleave", (e) => {
      if (!row.contains(e.relatedTarget)) row.classList.remove("step-drop-before");
    });

    row.addEventListener("drop", (e) => {
      e.preventDefault();
      const from = stepDragFromIndex;
      const to = rowIndex();
      stepDragFromIndex = null;
      clearStepDropIndicators();
      if (from === null || from === to) return;
      reorderStep(from, to);
    });
  });
}

function renderStepRow(step, index) {
  const row = document.createElement("div");
  row.className = "step-row";
  row.dataset.stepIndex = String(index);

  const handle = document.createElement("button");
  handle.type = "button";
  handle.className = "step-drag-handle";
  handle.draggable = true;
  handle.title = "Drag to reorder";
  handle.setAttribute("aria-label", `Drag step ${index + 1} to reorder`);
  if (typeof icon === "function") {
    handle.appendChild(icon("grip", "icon"));
  } else {
    handle.textContent = "⋮⋮";
  }
  row.appendChild(handle);

  const typeSelect = document.createElement("select");
  typeSelect.className = "step-type-select";
  typeSelect.dataset.field = "action";
  STEP_TYPES.forEach((t) => {
    const o = document.createElement("option");
    o.value = t;
    o.textContent = t;
    if (step.action === t) o.selected = true;
    typeSelect.appendChild(o);
  });
  typeSelect.addEventListener("change", () => changeStepType(index, typeSelect.value));
  const typeWrap = document.createElement("div");
  typeWrap.className = "field-labeled step-type-col";
  const typeLabRow = document.createElement("div");
  typeLabRow.className = "label-row";
  const typeLab = document.createElement("span");
  typeLab.className = "field-label";
  typeLab.textContent = "Step type";
  typeLabRow.appendChild(typeLab);
  typeWrap.appendChild(typeLabRow);
  typeWrap.appendChild(typeSelect);
  row.appendChild(typeWrap);

  const fields = document.createElement("div");
  fields.className = "step-fields";

  if (step.action === "goto") {
    fields.appendChild(labeledField("url", "URL", step.url || "", "url", "", "step.goto.url"));
  } else if (step.action === "delay") {
    fields.appendChild(
      labeledField("min", "Min (s)", step.min ?? 0.5, "number", "Shortest random wait", "step.delay.min")
    );
    fields.appendChild(
      labeledField("max", "Max (s)", step.max ?? 1.2, "number", "Longest random wait", "step.delay.max")
    );
    fields.appendChild(
      labeledSelect(
        "distribution",
        "Random style",
        step.distribution || "uniform",
        ["uniform", "triangular", "log_normal"],
        "How waits are picked between min and max",
        "step.delay.distribution"
      )
    );
    fields.appendChild(
      collapsibleFieldGroup(
        "Long pause (optional)",
        [
          labeledField(
            "long_pause_chance",
            "Chance (0–1)",
            step.long_pause_chance ?? 0,
            "number",
            "Probability of an extra distraction pause",
            "step.delay.long_pause"
          ),
          labeledField(
            "long_pause_min",
            "Pause min (s)",
            step.long_pause_min ?? 2,
            "number",
            "",
            "step.delay.long_pause"
          ),
          labeledField(
            "long_pause_max",
            "Pause max (s)",
            step.long_pause_max ?? 5,
            "number",
            "",
            "step.delay.long_pause"
          ),
        ],
        { open: (step.long_pause_chance ?? 0) > 0 }
      )
    );
  } else if (step.action === "scroll") {
    fields.appendChild(
      labeledField(
        "delta_y",
        "Pixels (delta Y)",
        step.delta_y ?? 300,
        "number",
        "Positive = down, negative = up",
        "step.scroll.delta_y"
      )
    );
    fields.appendChild(
      collapsibleFieldGroup(
        "Wheel ticks",
        [
          labeledField(
            "steps_min",
            "Min ticks",
            step.steps_min ?? 3,
            "number",
            "Fewest mouse-wheel steps",
            "step.scroll.ticks"
          ),
          labeledField(
            "steps_max",
            "Max ticks",
            step.steps_max ?? 8,
            "number",
            "Most mouse-wheel steps",
            "step.scroll.ticks"
          ),
          labeledField(
            "step_delay_min",
            "Tick delay min (s)",
            step.step_delay_min ?? 0.06,
            "number",
            "Pause between ticks (shortest)",
            "step.scroll.ticks"
          ),
          labeledField(
            "step_delay_max",
            "Tick delay max (s)",
            step.step_delay_max ?? 0.32,
            "number",
            "Pause between ticks (longest)",
            "step.scroll.ticks"
          ),
        ],
        { open: false }
      )
    );
    fields.appendChild(
      collapsibleFieldGroup(
        "Overscroll",
        [
          fieldCheckbox(
            "overscroll",
            "Overscroll then correct",
            step.overscroll !== false,
            "Scroll slightly past target, then scroll back",
            "step.scroll.overscroll"
          ),
          labeledField(
            "overscroll_ratio_min",
            "Overshoot min",
            step.overscroll_ratio_min ?? 0.06,
            "number",
            "Fraction of total scroll (e.g. 0.1 = 10%)",
            "step.scroll.overscroll"
          ),
          labeledField(
            "overscroll_ratio_max",
            "Overshoot max",
            step.overscroll_ratio_max ?? 0.16,
            "number",
            "",
            "step.scroll.overscroll"
          ),
        ],
        { open: step.overscroll === false }
      )
    );
    fields.appendChild(
      collapsibleFieldGroup(
        "After scroll",
        [
          labeledField(
            "pause_after_min",
            "Pause min (s)",
            step.pause_after_min ?? 0.2,
            "number",
            "",
            "step.scroll.after"
          ),
          labeledField(
            "pause_after_max",
            "Pause max (s)",
            step.pause_after_max ?? 0.85,
            "number",
            "",
            "step.scroll.after"
          ),
          fieldCheckbox(
            "variable_step_size",
            "Variable tick size",
            step.variable_step_size !== false,
            "Each wheel tick moves a random amount",
            "step.scroll.after"
          ),
        ],
        { open: false }
      )
    );
  } else if (step.action === "click") {
    if (!step.by) step.by = "role";
    appendLocatorFields(fields, step, false, index);
  } else if (step.action === "fill") {
    if (!step.by) step.by = "css";
    appendLocatorFields(fields, step, true, index);
  } else if (step.action === "run_scenario") {
    const cur = $("build-name").value.trim();
    const opts = scenarios
      .filter((s) => (s.type === "json" || s.type === "python") && s.name !== cur)
      .map((s) => s.name);
    fields.appendChild(
      labeledSelect(
        "scenario",
        "Flow to run",
        step.scenario || "",
        opts,
        "Runs another saved JSON or Python flow inline",
        "step.run_scenario"
      )
    );
    fields.appendChild(
      fieldCheckbox(
        "inherit_delays",
        "Use parent random-between-step delays",
        !!step.inherit_delays,
        "Otherwise use the nested flow’s delay settings",
        null
      )
    );
    fields.appendChild(
      fieldCheckbox(
        "skip_start_url",
        "Skip nested start URL goto",
        step.skip_start_url !== false,
        "Avoid duplicate navigation when composing flows",
        null
      )
    );
  } else if (step.action === "submit_form") {
    fields.appendChild(
      labeledSelect(
        "method",
        "Form method",
        step.method || "post",
        ["get", "post"],
        "",
        "step.submit_form.method"
      )
    );
    fields.appendChild(
      labeledField(
        "submit_name",
        "Submit button name",
        step.submit_name || "",
        "text",
        "",
        "step.submit_form.submit"
      )
    );
    fields.appendChild(
      collapsibleFieldGroup(
        "Selectors (optional)",
        [
          labeledField(
            "form_selector",
            "Form CSS selector",
            step.form_selector || "",
            "text",
            "",
            "step.submit_form.form_selector"
          ),
          labeledField(
            "submit_selector",
            "Submit CSS selector",
            step.submit_selector || "",
            "text",
            "",
            "step.submit_form.submit"
          ),
        ],
        { open: !!(step.form_selector || step.submit_selector) }
      )
    );

    const fieldsLabelRow = document.createElement("div");
    fieldsLabelRow.className = "form-fields-label label-row";
    const fieldsLabel = document.createElement("span");
    fieldsLabel.className = "form-fields-label";
    fieldsLabel.textContent = "Fields:";
    fieldsLabelRow.appendChild(fieldsLabel);
    fields.appendChild(fieldsLabelRow);

    const fieldsWrap = document.createElement("div");
    fieldsWrap.className = "form-fields-wrap";
    (step.fields || []).forEach((f, fi) => {
      fieldsWrap.appendChild(renderFormFieldRow(index, fi, f));
    });
    fields.appendChild(fieldsWrap);

    const addField = document.createElement("button");
    addField.type = "button";
    addField.className = "btn-add-field success outline";
    addField.onclick = (e) => {
      e.stopPropagation();
      if (!builderSteps[index].fields) builderSteps[index].fields = [];
      builderSteps[index].fields.push({ by: "css", selector: "", value: "" });
      renderSteps();
    };
    if (typeof enhanceButton === "function") {
      enhanceButton(addField, "plus", { label: "Add field" });
    } else {
      addField.textContent = "+ field";
    }
    fields.appendChild(addField);
  }

  row.appendChild(fields);

  const actions = document.createElement("div");
  actions.className = "step-actions";
  if (typeof makeIconButton === "function") {
    actions.appendChild(
      makeIconButton("trash", "Remove step", () => removeStep(index), { danger: true })
    );
  } else {
    actions.innerHTML = `
      <button type="button" class="danger" data-del title="Remove step">×</button>
    `;
    actions.querySelector("[data-del]").onclick = () => removeStep(index);
  }
  row.appendChild(actions);

  fields.querySelectorAll("input, select").forEach((inp) => {
    inp.addEventListener("change", () => syncStepFromDom(index, row));
    inp.addEventListener("input", () => syncStepFromDom(index, row));
  });

  return row;
}

function fieldInput(name, value, type = "text") {
  const inp = document.createElement("input");
  inp.type = type;
  inp.dataset.field = name;
  inp.value = value ?? "";
  return inp;
}

function fieldSelect(name, value, options) {
  const sel = document.createElement("select");
  sel.dataset.field = name;
  options.forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    if (value === v) o.selected = true;
    sel.appendChild(o);
  });
  return sel;
}

/** Collapsible group of fields inside a step row (native details/summary). */
function collapsibleFieldGroup(title, nodes, options = {}) {
  const { open = false } = options;
  const details = document.createElement("details");
  details.className = "step-fields-collapsible";
  if (open) details.open = true;
  const summary = document.createElement("summary");
  summary.className = "step-fields-collapsible-summary";
  summary.textContent = title;
  details.appendChild(summary);
  const body = document.createElement("div");
  body.className = "step-fields-collapsible-body";
  for (const node of nodes) body.appendChild(node);
  details.appendChild(body);
  return details;
}

function appendFieldLabel(parent, labelText, hint, helpId) {
  const row = document.createElement("div");
  row.className = "label-row";
  const lab = document.createElement("span");
  lab.className = "field-label";
  lab.textContent = labelText;
  if (hint) lab.title = hint;
  row.appendChild(lab);
  parent.appendChild(row);
}

function labeledField(name, labelText, value, type = "text", hint = "", helpId = null) {
  const wrap = document.createElement("div");
  wrap.className = "field-labeled";
  appendFieldLabel(wrap, labelText, hint, helpId);
  const inp = fieldInput(name, value, type);
  if (hint) inp.title = hint;
  wrap.appendChild(inp);
  return wrap;
}

function labeledSelect(name, labelText, value, options, hint = "", helpId = null) {
  const wrap = document.createElement("div");
  wrap.className = "field-labeled";
  appendFieldLabel(wrap, labelText, hint, helpId);
  const sel = fieldSelect(name, value, options);
  if (hint) sel.title = hint;
  wrap.appendChild(sel);
  return wrap;
}

function fieldCheckbox(name, labelText, checked, hint = "", helpId = null) {
  const label = document.createElement("label");
  label.className = "checkbox inline field-labeled";
  const inp = document.createElement("input");
  inp.type = "checkbox";
  inp.dataset.field = name;
  inp.checked = !!checked;
  if (hint) inp.title = hint;
  label.appendChild(inp);
  const span = document.createElement("span");
  span.className = "field-label";
  span.textContent = labelText;
  label.appendChild(span);
  return label;
}

function syncStepFromDom(index, row) {
  const prev = builderSteps[index];
  const action =
    row.querySelector('[data-field="action"]')?.value || prev.action;
  const step = { action };
  row.querySelectorAll("[data-field]").forEach((el) => {
    const key = el.dataset.field;
    if (key === "action") return;
    if (el.type === "checkbox") {
      step[key] = el.checked;
      return;
    }
    let val = el.value;
    if (el.type === "number") val = parseFloat(val);
    if (val !== "" && val !== null && !Number.isNaN(val)) step[key] = val;
  });
  if (prev.action === "submit_form" && prev.fields) {
    step.fields = prev.fields;
  }
  builderSteps[index] = step;
}

function renderSteps() {
  const list = $("steps-list");
  list.innerHTML = "";
  builderSteps.forEach((step, i) => list.appendChild(renderStepRow(step, i)));
  initStepDragDrop(list);
}

function removeStep(index) {
  builderSteps.splice(index, 1);
  renderSteps();
}

function scenarioFieldInput(name, value, type = "text") {
  const inp = fieldInput(name, value, type);
  delete inp.dataset.field;
  inp.dataset.scenarioField = name;
  return inp;
}

function labeledScenarioField(name, labelText, value, type = "text", hint = "", helpId = null) {
  const wrap = document.createElement("div");
  wrap.className = "field-labeled";
  const topicId =
    helpId ||
    (name === "between_steps_min"
      ? "scenario.between_steps_min"
      : name === "between_steps_max"
        ? "scenario.between_steps_max"
        : null);
  appendFieldLabel(wrap, labelText, hint, topicId);
  const inp = scenarioFieldInput(name, value, type);
  if (hint) inp.title = hint;
  wrap.appendChild(inp);
  return wrap;
}

function labeledScenarioSelect(name, labelText, value, options, hint = "", helpId = null) {
  const wrap = document.createElement("div");
  wrap.className = "field-labeled";
  appendFieldLabel(wrap, labelText, hint, helpId || "scenario.between_steps_distribution");
  const sel = fieldSelect(name, value, options);
  delete sel.dataset.field;
  sel.dataset.scenarioField = name;
  if (hint) sel.title = hint;
  wrap.appendChild(sel);
  return wrap;
}

function readScenarioOptions() {
  const opts = {
    random_delay_between_steps: $("build-random-between-steps").checked,
  };
  if (!opts.random_delay_between_steps) return opts;
  $("between-steps-fields").querySelectorAll("[data-scenario-field]").forEach((el) => {
    const key = el.dataset.scenarioField;
    let val = el.value;
    if (el.type === "number") val = parseFloat(val);
    if (val !== "" && val !== null && !Number.isNaN(val)) opts[key] = val;
  });
  return opts;
}

function renderScenarioOptions(doc = {}) {
  const enabled = !!doc.random_delay_between_steps;
  $("build-random-between-steps").checked = enabled;
  const container = $("between-steps-fields");
  container.innerHTML = "";
  container.classList.toggle("hidden", !enabled);
  if (!enabled) return;
  container.appendChild(
    labeledScenarioField(
      "between_steps_min",
      "Min (s)",
      doc.between_steps_min ?? 0.3,
      "number",
      "Shortest pause before the next step"
    )
  );
  container.appendChild(
    labeledScenarioField(
      "between_steps_max",
      "Max (s)",
      doc.between_steps_max ?? 1.2,
      "number",
      "Longest pause before the next step"
    )
  );
  container.appendChild(
    labeledScenarioSelect(
      "between_steps_distribution",
      "Random style",
      doc.between_steps_distribution || "triangular",
      ["uniform", "triangular", "log_normal"],
      "How pauses are picked between min and max"
    )
  );
}

function collectDocument() {
  return {
    name: $("build-name").value.trim(),
    description: $("build-desc").value.trim(),
    start_url: $("build-url").value.trim(),
    steps: builderSteps.map((s) => normalizeStep({ ...s })),
    ...readScenarioOptions(),
  };
}

async function savePythonScenario() {
  const name = $("build-name").value.trim();
  const source = getPythonSource();
  if (!name) {
    $("build-msg-python").textContent = "Name is required";
    return;
  }
  if (name === DRAFT_SCENARIO_ID) {
    $("build-msg-python").textContent = "Choose a different flow name";
    return;
  }
  await api(`/api/scenarios/${encodeURIComponent(name)}/python-source`, {
    method: "PUT",
    body: JSON.stringify({ source }),
  });
  const wasDraft = isDraftSelected();
  draftIsPython = false;
  $("build-msg-python").textContent = `Saved "${name}"`;
  selectedScenario = name;
  await loadScenarios();
  if (wasDraft) {
    renderScenarioList("scenario-list", scenarioListOnSelect);
  }
  setSelectedScenario(name);
  updateFlowNameReadonly();
}

async function saveScenario() {
  const doc = collectDocument();
  if (!doc.name) {
    $("build-msg").textContent = "Name is required";
    return;
  }
  if (doc.name === DRAFT_SCENARIO_ID) {
    $("build-msg").textContent = "Choose a different scenario name";
    return;
  }
  await api("/api/scenarios", { method: "POST", body: JSON.stringify(doc) });
  const wasDraft = isDraftSelected();
  $("build-msg").textContent = `Saved "${doc.name}"`;
  selectedScenario = doc.name;
  await loadScenarios();
  if (wasDraft) {
    renderScenarioList("scenario-list", scenarioListOnSelect);
  }
  setSelectedScenario(doc.name);
}


async function startRun(scenarioName) {
  const scenario = scenarioName || getSelectedScenario();
  if (!scenario) return;
  const body = {
    scenario,
    loops: parseInt($("run-loops").value, 10) || 1,
    pause_between_loops_sec: parseFloat($("run-pause").value) || 0,
    headless: $("run-headless").checked,
    channel: "chrome",
    slow_mo: 0,
  };
  $("log-output").textContent = "";
  await initRunStepProgress(scenario);
  await api("/api/run", { method: "POST", body: JSON.stringify(body) });
  startRunStatusPolling();
  try {
    await refreshRunStepProgressFromServer();
  } catch {
    /* polling / websocket will catch up */
  }
}

function setMainTab(which) {
  const isWorkspace = which === "workspace";
  $("panel-main")?.classList.toggle("active", isWorkspace);
  $("panel-groups")?.classList.toggle("active", !isWorkspace);
  $("tab-workspace")?.classList.toggle("active", isWorkspace);
  $("tab-groups")?.classList.toggle("active", !isWorkspace);
  $("tab-workspace")?.setAttribute("aria-selected", isWorkspace ? "true" : "false");
  $("tab-groups")?.setAttribute("aria-selected", !isWorkspace ? "true" : "false");
  $("panel-main")?.setAttribute("aria-hidden", !isWorkspace ? "true" : "false");
  $("panel-groups")?.setAttribute("aria-hidden", isWorkspace ? "true" : "false");
}

function closeNewFlowDropdown() {
  const drop = $("new-flow-dropdown");
  if (drop) drop.open = false;
}

/** @type {Array<{id:string,label:string,scenario_names:string[]}>} */
let groupsModalDraft = [];

function renderGroupsModalEditor() {
  const body = $("groups-editor-body");
  if (!body) return;
  body.innerHTML = "";
  groupsModalDraft.forEach((g, gi) => {
    const row = document.createElement("div");
    row.className = "groups-modal-row card";

    const idLab = document.createElement("label");
    idLab.className = "field-label";
    idLab.textContent = "Group id";
    const idInp = document.createElement("input");
    idInp.type = "text";
    idInp.value = g.id || "";
    idInp.placeholder = "my_group";
    idInp.addEventListener("input", () => {
      groupsModalDraft[gi].id = idInp.value.trim();
    });

    const labLab = document.createElement("label");
    labLab.className = "field-label";
    labLab.textContent = "Label";
    const labInp = document.createElement("input");
    labInp.type = "text";
    labInp.value = g.label || "";
    labInp.addEventListener("input", () => {
      groupsModalDraft[gi].label = labInp.value.trim();
    });

    const selLab = document.createElement("label");
    selLab.className = "field-label";
    selLab.textContent = "Flows in group (multi-select)";
    const sel = document.createElement("select");
    sel.multiple = true;
    const names = scenarios.filter((s) => s.type === "json" || s.type === "python").map((s) => s.name);
    sel.size = Math.min(12, Math.max(4, names.length || 4));
    names.forEach((nm) => {
      const o = document.createElement("option");
      o.value = nm;
      o.textContent = nm;
      o.selected = (g.scenario_names || []).includes(nm);
      sel.appendChild(o);
    });
    sel.addEventListener("change", () => {
      groupsModalDraft[gi].scenario_names = Array.from(sel.selectedOptions).map((o) => o.value);
    });

    const del = document.createElement("button");
    del.type = "button";
    del.className = "danger outline";
    del.textContent = "Remove group";
    del.addEventListener("click", () => {
      groupsModalDraft.splice(gi, 1);
      renderGroupsModalEditor();
    });

    row.appendChild(idLab);
    row.appendChild(idInp);
    row.appendChild(labLab);
    row.appendChild(labInp);
    row.appendChild(selLab);
    row.appendChild(sel);
    row.appendChild(del);
    body.appendChild(row);
  });

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "success outline";
  addBtn.textContent = "+ Add group";
  addBtn.addEventListener("click", () => {
    groupsModalDraft.push({ id: `g_${Date.now()}`, label: "New group", scenario_names: [] });
    renderGroupsModalEditor();
  });
  body.appendChild(addBtn);
}

function openGroupsPanel() {
  $("groups-msg").textContent = "";
  groupsModalDraft = structuredClone(groupsData.groups || []);
  renderGroupsModalEditor();
  setMainTab("groups");
}

async function saveGroupsModal() {
  $("groups-msg").textContent = "";
  await api("/api/groups", {
    method: "PUT",
    body: JSON.stringify({ groups: groupsModalDraft }),
  });
  await loadGroups();
  renderScenarioList("scenario-list", scenarioListOnSelect);
  $("groups-msg").textContent = "Groups saved.";
  $("build-msg").textContent = "Groups saved.";
}

async function startRunGroup(groupId) {
  const body = {
    group_id: groupId,
    loops: parseInt($("run-loops").value, 10) || 1,
    pause_between_loops_sec: parseFloat($("run-pause").value) || 0,
    pause_between_flows_sec: parseFloat($("run-pause-flows")?.value || "0") || 0,
    headless: $("run-headless").checked,
    channel: "chrome",
    slow_mo: 0,
  };
  $("log-output").textContent = "";
  await initRunStepProgress(`group:${groupId}`);
  await api("/api/run/group", { method: "POST", body: JSON.stringify(body) });
  startRunStatusPolling();
  try {
    await refreshRunStepProgressFromServer();
  } catch {
    /* polling / websocket will catch up */
  }
}

$("btn-start").onclick = () => startRun();
$("btn-stop").onclick = () => api("/api/run/stop", { method: "POST" });
$("tab-workspace")?.addEventListener("click", () => setMainTab("workspace"));
$("tab-groups")?.addEventListener("click", () => openGroupsPanel());
$("groups-save")?.addEventListener("click", () =>
  saveGroupsModal().catch((e) => ($("groups-msg").textContent = e.message))
);
$("groups-back")?.addEventListener("click", () => setMainTab("workspace"));
$("btn-add-step").onclick = () => {
  const last = builderSteps[builderSteps.length - 1];
  builderSteps.push(defaultStep(last?.action || "goto"));
  renderSteps();
};
$("btn-save").onclick = () => saveScenario().catch((e) => ($("build-msg").textContent = e.message));
$("btn-new-flow")?.addEventListener("click", () => {
  closeNewFlowDropdown();
  newFlow();
});
$("btn-new-python-flow")?.addEventListener("click", () => {
  closeNewFlowDropdown();
  newPythonFlow();
});
$("btn-save-python")?.addEventListener("click", () =>
  savePythonScenario().catch((e) => ($("build-msg-python").textContent = e.message))
);
$("btn-delete-flow")?.addEventListener("click", () =>
  deleteSelectedFlow().catch((e) => ($("build-msg").textContent = e.message))
);
$("btn-test-run").onclick = async () => {
  try {
    await saveScenario();
    await startRun($("build-name").value.trim());
  } catch (e) {
    $("build-msg").textContent = e.message;
  }
};
$("btn-test-run-python")?.addEventListener("click", async () => {
  try {
    await savePythonScenario();
    await startRun($("build-name").value.trim());
  } catch (e) {
    $("build-msg-python").textContent = e.message;
  }
});

(async () => {
  try {
    initPythonCodeMirror();
    await loadHealth();
    await loadScenarios();
    const st = await api("/api/run/status");
    setRunStatus(st);
    updateRunButtons(st.state);
    if (st.state === "running" && st.scenario) {
      await initRunStepProgress(st.scenario);
      applyRunStepProgress(st);
      startRunStatusPolling();
    } else if (st.step_progress?.length) {
      runStepProgress = st.step_progress.map((s) => ({ ...s }));
      runShowStepProgress = true;
      setRunProgressVisible(true);
    }
    connectWebSocket();
    if (selectedScenario) {
      await loadFlowIntoEditor(selectedScenario);
      if (runShowStepProgress && runStepProgress?.length) renderRunProgressPanel();
    } else {
      newFlow();
    }
    $("build-random-between-steps").addEventListener("change", () => renderScenarioOptions(readScenarioOptions()));
    $("build-name")?.addEventListener("input", syncDraftListLabel);
    $("build-desc")?.addEventListener("input", syncDraftListLabel);

    document.addEventListener("click", (e) => {
      const drop = $("new-flow-dropdown");
      if (!drop?.open) return;
      if (drop.contains(e.target)) return;
      drop.open = false;
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      closeNewFlowDropdown();
    });
  } catch (e) {
    $("health").textContent = "Failed to connect: " + e.message;
  }
})();
