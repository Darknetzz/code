const $ = (id) => document.getElementById(id);

const STORAGE_RUN_OPTIONS = "webbot.runOptions";
const STORAGE_THEME = "webbot.theme";

function formatApiDetail(detail) {
  if (detail == null) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((x) => {
        if (typeof x === "object" && x !== null && "msg" in x) return String(x.msg);
        return JSON.stringify(x);
      })
      .join("; ");
  }
  if (typeof detail === "object" && "msg" in detail) return String(detail.msg);
  return String(detail);
}

let _toastSeq = 0;
function showToast(message, variant = "error") {
  const region = $("toast-region");
  if (!region) return;
  const el = document.createElement("div");
  el.id = `toast-${++_toastSeq}`;
  el.className = `toast toast-${variant}`;
  el.setAttribute("role", "alert");
  el.textContent = message;
  region.appendChild(el);
  const ms = variant === "error" ? 8000 : 4500;
  setTimeout(() => el.remove(), ms);
}

function showError(message) {
  showToast(message, "error");
}

function showSuccess(message) {
  showToast(message, "success");
}

function showConfirmAsync(message, options = {}) {
  const { title = "Confirm", danger = false } = options;
  const dlg = $("confirm-dialog");
  const titleEl = $("confirm-dialog-title");
  const msgEl = $("confirm-dialog-message");
  const okBtn = $("confirm-dialog-ok");
  if (!dlg || !titleEl || !msgEl || !okBtn) return Promise.resolve(false);
  titleEl.textContent = title;
  msgEl.textContent = message;
  okBtn.classList.toggle("danger", danger);
  return new Promise((resolve) => {
    const onClose = () => {
      dlg.removeEventListener("close", onClose);
      resolve(dlg.returnValue === "confirm");
    };
    dlg.addEventListener("close", onClose);
    dlg.showModal();
    okBtn.focus();
  });
}

function downloadText(filename, text, mime = "text/plain;charset=utf-8") {
  const blob = new Blob([text], { type: mime });
  const a = document.createElement("a");
  const url = URL.createObjectURL(blob);
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function uniqueScenarioName(baseStem) {
  const base = String(baseStem || "flow").trim() || "flow";
  let candidate = base;
  let n = 2;
  while (scenarios.some((s) => s.name === candidate)) {
    candidate = `${base}_${n}`;
    n += 1;
  }
  return candidate;
}

function normalizeImportedJsonDoc(raw) {
  if (!raw || typeof raw !== "object") throw new Error("Invalid JSON flow: expected an object");
  const name = String(raw.name ?? "").trim();
  if (!name) throw new Error('Invalid JSON flow: missing "name"');
  if (!Array.isArray(raw.steps)) throw new Error('Invalid JSON flow: missing "steps" array');
  return {
    name,
    description: String(raw.description ?? ""),
    start_url: String(raw.start_url ?? ""),
    steps: raw.steps,
    random_delay_between_steps: Boolean(raw.random_delay_between_steps),
    between_steps_min: typeof raw.between_steps_min === "number" ? raw.between_steps_min : 0.3,
    between_steps_max: typeof raw.between_steps_max === "number" ? raw.between_steps_max : 1.2,
    between_steps_distribution:
      raw.between_steps_distribution === "uniform" ||
      raw.between_steps_distribution === "triangular" ||
      raw.between_steps_distribution === "log_normal"
        ? raw.between_steps_distribution
        : "triangular",
  };
}

function isHelpFilterShortcutsTarget(el) {
  if (!el) return false;
  if (el.id === "flow-list-filter") return true;
  if (el.closest?.("#help-dialog")) return true;
  if (el.closest?.("#confirm-dialog")) return true;
  return false;
}

function syncCodeMirrorTheme() {
  if (!pythonCodeMirror || typeof CodeMirror === "undefined") return;
  const light = document.documentElement.getAttribute("data-theme") === "light";
  pythonCodeMirror.setOption("theme", light ? "default" : "dracula");
}

function applyTheme(mode) {
  const light = mode === "light";
  if (light) document.documentElement.setAttribute("data-theme", "light");
  else document.documentElement.removeAttribute("data-theme");
  try {
    localStorage.setItem(STORAGE_THEME, light ? "light" : "dark");
  } catch (_) {}
  syncCodeMirrorTheme();
  const btn = $("btn-theme");
  if (btn) btn.textContent = light ? "Dark" : "Light";
}

function toggleTheme() {
  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  applyTheme(isLight ? "dark" : "light");
}

function readRunOptionsFromForm() {
  return {
    loops: parseInt($("run-loops")?.value, 10) || 1,
    pause_between_loops: parseFloat($("run-pause")?.value) || 0,
    pause_between_flows: parseFloat($("run-pause-flows")?.value) || 0,
    channel: $("run-channel")?.value?.trim() || "chrome",
    slow_mo: Math.max(0, parseInt($("run-slow-mo")?.value, 10) || 0),
    headless: $("run-headless")?.checked ?? false,
    ignore_https_errors: $("run-ignore-https-errors")?.checked ?? false,
    keep_session_open: $("run-keep-session-open")?.checked ?? false,
  };
}

function applyRunOptionsToForm(o) {
  if (!o || typeof o !== "object") return;
  const loops = $("run-loops");
  if (loops) loops.value = String(Math.max(1, o.loops ?? 1));
  const pause = $("run-pause");
  if (pause) pause.value = String(Math.max(0, o.pause_between_loops ?? 0));
  const pauseFlows = $("run-pause-flows");
  if (pauseFlows) pauseFlows.value = String(Math.max(0, o.pause_between_flows ?? 0));
  const ch = $("run-channel");
  if (ch && o.channel) ch.value = o.channel;
  const sm = $("run-slow-mo");
  if (sm) sm.value = String(Math.max(0, o.slow_mo ?? 0));
  const head = $("run-headless");
  if (head) head.checked = Boolean(o.headless);
  const ign = $("run-ignore-https-errors");
  if (ign) ign.checked = Boolean(o.ignore_https_errors);
  const kso = $("run-keep-session-open");
  if (kso) kso.checked = Boolean(o.keep_session_open);
}

function persistRunOptions() {
  try {
    localStorage.setItem(STORAGE_RUN_OPTIONS, JSON.stringify(readRunOptionsFromForm()));
  } catch (_) {}
}

function loadPersistedRunOptions() {
  try {
    const raw = localStorage.getItem(STORAGE_RUN_OPTIONS);
    if (!raw) return;
    applyRunOptionsToForm(JSON.parse(raw));
  } catch (_) {}
}

function wireRunOptionsPersistence() {
  const ids = ["run-loops", "run-pause", "run-pause-flows", "run-channel", "run-slow-mo"];
  for (const id of ids) {
    const el = $(id);
    if (!el) continue;
    el.addEventListener("change", persistRunOptions);
    el.addEventListener("input", persistRunOptions);
  }
  $("run-headless")?.addEventListener("change", persistRunOptions);
  $("run-ignore-https-errors")?.addEventListener("change", persistRunOptions);
  $("run-keep-session-open")?.addEventListener("change", persistRunOptions);
}

async function maybeConfirmDiscardForImport() {
  const dirty =
    selectedScenario &&
    savedFlowBaseline !== null &&
    captureCurrentFlowSnapshot() !== savedFlowBaseline;
  if (!dirty) return true;
  return showConfirmAsync("Discard unsaved changes and import a file?", { title: "Import flow" });
}

let importTargetKind = "json";

/** Last-synced editor payload for the active flow (save/load); used to detect unsaved edits. */
let savedFlowBaseline = null;

function captureCurrentFlowSnapshot() {
  if (isPythonUi()) {
    return `py:${getPythonSource()}`;
  }
  return `json:${JSON.stringify(collectDocument())}`;
}

function commitSavedBaseline() {
  if (!selectedScenario) {
    savedFlowBaseline = null;
    syncUnsavedIndicators();
    return;
  }
  savedFlowBaseline = captureCurrentFlowSnapshot();
  syncUnsavedIndicators();
}

function syncUnsavedIndicators() {
  const dirty =
    selectedScenario &&
    savedFlowBaseline !== null &&
    captureCurrentFlowSnapshot() !== savedFlowBaseline;
  document.querySelectorAll(".scenario-item").forEach((btn) => {
    const on = selectedScenario && btn.dataset.name === selectedScenario;
    btn.classList.toggle("scenario-item-unsaved", on && dirty);
  });
}

/** Client-only id for an unsaved flow row in the list. */
const DRAFT_SCENARIO_ID = "__draft__";

let scenarios = [];
/** @type {{ groups: Array<{id:string,label:string,scenario_names:string[]}>, ungrouped: string[] }} */
let groupsData = { groups: [], ungrouped: [] };
let selectedScenario = null;
let builderSteps = [];
/** Opt-in UI: show the workflow label field while the label text is still empty (WeakMap — never serialized). */
const workflowLabelUiExpandedByStepRef = new WeakMap();
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
    theme: document.documentElement.getAttribute("data-theme") === "light" ? "default" : "dracula",
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: true,
    matchBrackets: true,
    viewportMargin: 80,
    extraKeys: {
      Tab: (cm) => cm.replaceSelection("    ", "end"),
      "Shift-Tab": "indentLess",
    },
  });
  pythonCodeMirror.on("change", () => syncUnsavedIndicators());
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

function onBuildNameDescInput() {
  syncDraftListLabel();
  syncUnsavedIndicators();
}

function scenarioListOnSelect(name) {
  void selectScenario(name).catch((e) => showError(e.message));
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
    case "open_url":
      return `open ${step.url || "?"}`;
    case "goto":
      return `goto › ${step.goto_label || "?"}`;
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
    case "if_present":
      return `if_present (${step.by || "?"} …)`;
    case "exit":
      return step.message ? `exit: ${step.message}` : "exit";
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
    case "skipped":
      return "–";
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
  if (!runIsBusy(st.state)) stopRunStatusPolling();
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
  const m = line.match(/\[(?:\.\.|OK|FAIL|SKIP)\](?:.*?)step (\d+)\/(\d+):\s*(.+?)(?:\s+-\s+(.+))?$/);
  if (!m) return;
  const index = parseInt(m[1], 10);
  const label = m[3].trim();
  const err = m[4]?.trim() || null;
  let status = "running";
  if (line.startsWith("[OK]")) status = "ok";
  else if (line.startsWith("[FAIL]")) status = "failed";
  else if (line.startsWith("[SKIP]")) status = "skipped";

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
    (msg.state === "completed" ||
      msg.state === "holding_session" ||
      msg.state === "failed" ||
      msg.state === "stopped")
  ) {
    if (msg.state === "completed" || msg.state === "holding_session") {
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
    if (el.classList.contains("btn-delete-flow")) return;
    if (el.id === "btn-save" || el.id === "btn-test-run" || el.id === "btn-add-step") {
      el.disabled = disable;
    } else if (!el.closest(".step-actions")) {
      el.disabled = disable;
    }
  });
  updateDeleteFlowButton();
}

function updateDeleteFlowButton() {
  document.querySelectorAll(".btn-delete-flow").forEach((btn) => {
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
  });
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
  builderSteps = [defaultStep("open_url")];
  renderSteps();
}

async function newFlow() {
  draftIsPython = false;
  if (isDraftSelected()) {
    if (!(await showConfirmAsync("Discard current draft and start a new one?"))) return;
    clearFlowEditor();
    $("build-msg").textContent = "Draft — enter a name and save.";
    syncDraftListLabel();
    syncFlowKindSelectFromDraftOrScenario();
    commitSavedBaseline();
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
  commitSavedBaseline();
}

async function newPythonFlow() {
  if (isDraftSelected()) {
    if (!(await showConfirmAsync("Discard current draft and start a new Python draft?"))) return;
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
    syncFlowKindSelectFromDraftOrScenario();
    commitSavedBaseline();
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
  commitSavedBaseline();
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
    commitSavedBaseline();
  }
}

async function selectScenario(name) {
  if (name === selectedScenario) return;
  const leavingDraft = isDraftSelected() && name !== DRAFT_SCENARIO_ID;
  if (leavingDraft && !(await showConfirmAsync("Discard unsaved draft?"))) return;
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
  savedFlowBaseline = null;
  syncUnsavedIndicators();
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
    commitSavedBaseline();
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
      commitSavedBaseline();
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
    commitSavedBaseline();
  } catch (e) {
    $("build-msg").textContent = e.message;
  }
}

async function deleteSelectedFlow() {
  if (isDraftSelected()) {
    if (!(await showConfirmAsync("Discard unsaved draft?"))) return;
    await discardDraft();
    $("build-msg").textContent = "Draft discarded";
    $("build-msg-python").textContent = "";
    return;
  }
  const name = selectedScenario;
  if (!name) return;
  if (
    !(await showConfirmAsync(`Delete flow "${name}"? This cannot be undone.`, {
      title: "Delete flow",
      danger: true,
    }))
  )
    return;
  await api(`/api/scenarios/${encodeURIComponent(name)}`, { method: "DELETE" });
  await loadScenarios();
  if (scenarios.length) await selectScenario(scenarios[0].name);
  else await newFlow();
  $("build-msg").textContent = `Deleted "${name}"`;
  $("build-msg-python").textContent = "";
}

function syncScenarioListSelection() {
  document.querySelectorAll(".scenario-item").forEach((btn) => {
    const on = selectedScenario && btn.dataset.name === selectedScenario;
    btn.classList.toggle("selected", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  syncUnsavedIndicators();
}

function syncFlowKindSelectFromDraftOrScenario() {
  const sel = $("build-flow-kind");
  if (!sel) return;
  if (selectedScenario === DRAFT_SCENARIO_ID) {
    sel.value = draftIsPython ? "python" : "json";
  } else if (selectedScenario) {
    const info = getScenarioInfo(selectedScenario);
    sel.value = info?.type === "python" ? "python" : "json";
  } else {
    sel.value = draftIsPython ? "python" : "json";
  }
  const canPickKind = isDraftSelected() || !selectedScenario;
  sel.disabled = !canPickKind;
  sel.title = canPickKind
    ? "Choose JSON step builder or Python source for a new flow."
    : "Saved flows are either .json or .py — type is fixed. Use New flow to create the other kind.";
}

function setSelectedScenario(name, options = {}) {
  const prev = selectedScenario;
  selectedScenario = name || null;
  if (!selectedScenario) savedFlowBaseline = null;
  syncScenarioListSelection();
  updateDeleteFlowButton();
  syncFlowKindSelectFromDraftOrScenario();
  if (!options.skipPreview && prev !== selectedScenario) clearRunStepProgress();
}

async function createNewFlowFromToolbar() {
  const kind = $("build-flow-kind")?.value === "python" ? "python" : "json";
  if (kind === "python") await newPythonFlow();
  else await newFlow();
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
  const unsavedDot = document.createElement("span");
  unsavedDot.className = "scenario-unsaved-dot";
  unsavedDot.title = "Unsaved changes";

  const nameText = document.createElement("span");
  nameText.className = "scenario-item-name-text";
  nameText.textContent = s.displayName ?? s.name;
  nameEl.appendChild(unsavedDot);
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

function getFlowListSearchQuery() {
  return ($("flow-list-filter")?.value ?? "").trim().toLowerCase();
}

/** Match sidebar search against name, optional description, and optional displayName (drafts). */
function scenarioEntryMatchesSearch(entry) {
  const q = getFlowListSearchQuery();
  if (!q) return true;
  const name = String(entry.name ?? "").toLowerCase();
  const desc = String(entry.description ?? "").toLowerCase();
  const display = String(entry.displayName ?? "").toLowerCase();
  return name.includes(q) || desc.includes(q) || display.includes(q);
}

/** Max lines kept in the log panel before oldest entries are trimmed. */
const MAX_LOG_LINES = 4000;

function getRunPlaywrightOptions() {
  const chEl = $("run-channel");
  const smEl = $("run-slow-mo");
  const channel = chEl?.value?.trim() || "chrome";
  const slowMo = Math.max(0, parseInt(smEl?.value, 10) || 0);
  return { channel, slow_mo: slowMo };
}

/** Runner is blocking new starts while executing or holding the browser open. */
function runIsBusy(state) {
  return state === "running" || state === "holding_session";
}

function renderScenarioList(containerId, onSelect) {
  const list = $(containerId);
  if (!list) return;
  list.innerHTML = "";

  const draftRows = isDraftSelected() ? [getDraftListEntry()] : [];
  const editableFlows = scenarios.filter((s) => s.type === "json" || s.type === "python");
  const hasGroupStructure = groupsData.groups && groupsData.groups.length > 0;

  const showEmpty =
    draftRows.length === 0 && editableFlows.length === 0 && !hasGroupStructure;

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
        showError(err.message);
      });
    });

    summary.appendChild(lab);
    summary.appendChild(runGrp);
    details.appendChild(summary);

    const sub = document.createElement("ul");
    sub.className = "scenario-group-flows";
    const namesInGroup = (g.scenario_names || []).filter((nm) =>
      editableFlows.some((x) => x.name === nm)
    );
    let anyMemberShown = false;
    for (const nm of g.scenario_names || []) {
      const flow = editableFlows.find((x) => x.name === nm);
      if (!flow) continue;
      if (!scenarioEntryMatchesSearch(flow)) continue;
      anyMemberShown = true;
      sub.appendChild(buildScenarioListItem(flow, onSelect));
    }
    if (!anyMemberShown) {
      const hint = document.createElement("li");
      hint.className = "muted scenario-list-empty";
      hint.style.listStyle = "none";
      hint.textContent =
        namesInGroup.length && getFlowListSearchQuery()
          ? "No matching flows in this group"
          : "No flows in this group";
      sub.appendChild(hint);
    }
    details.appendChild(sub);
    wrap.appendChild(details);
    list.appendChild(wrap);
  }

  const ungrouped = (groupsData.ungrouped || []).filter((nm) =>
    editableFlows.some((x) => x.name === nm)
  );

  const ungroupedFlows = ungrouped
    .map((nm) => editableFlows.find((x) => x.name === nm))
    .filter(Boolean)
    .filter((f) => scenarioEntryMatchesSearch(f));

  if (ungrouped.length && ungroupedFlows.length) {
    const ugWrap = document.createElement("li");
    ugWrap.className = "scenario-list-group-wrap";
    const h = document.createElement("div");
    h.className = "scenario-ungrouped-heading muted field-label";
    h.textContent = "Ungrouped";
    ugWrap.appendChild(h);
    const ul = document.createElement("ul");
    ul.className = "scenario-group-flows";
    for (const flow of ungroupedFlows) {
      ul.appendChild(buildScenarioListItem(flow, onSelect));
    }
    ugWrap.appendChild(ul);
    list.appendChild(ugWrap);
  } else if (ungrouped.length && getFlowListSearchQuery()) {
    const ugWrap = document.createElement("li");
    ugWrap.className = "scenario-list-group-wrap";
    const h = document.createElement("div");
    h.className = "scenario-ungrouped-heading muted field-label";
    h.textContent = "Ungrouped";
    ugWrap.appendChild(h);
    const ul = document.createElement("ul");
    ul.className = "scenario-group-flows";
    const hint = document.createElement("li");
    hint.className = "muted scenario-list-empty";
    hint.style.listStyle = "none";
    hint.textContent = "No matching ungrouped flows";
    ul.appendChild(hint);
    ugWrap.appendChild(ul);
    list.appendChild(ugWrap);
  }

  syncScenarioListSelection();
}

function appendLog(line) {
  const el = $("log-output");
  if (!el) return;
  let text = el.textContent ? `${el.textContent}\n${line}` : line;
  const lines = text.split("\n");
  if (lines.length > MAX_LOG_LINES) {
    text = lines.slice(-MAX_LOG_LINES).join("\n");
  }
  el.textContent = text;
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
    holding_session: "Session open",
    completed: "Completed",
    failed: "Failed",
    stopped: "Stopped",
  };
  const detail = typeof msg === "object" ? formatRunDetail(msg) : "";
  el.textContent = (labels[state] || state) + (detail ? ` — ${detail}` : "");
}

function updateRunButtons(state) {
  const busy = runIsBusy(state);
  $("btn-start").disabled = busy || !getSelectedScenario();
  $("btn-stop").disabled = !busy;
}

async function api(path, options = {}) {
  const { headers: optHeaders, ...rest } = options;
  const res = await fetch(path, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...optHeaders,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail ?? res.statusText;
    const msg = formatApiDetail(detail);
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

async function loadHealth() {
  const h = await api("/api/health");
  const parts = [`v${h.version}`, `Playwright ${h.playwright ? "ok" : "missing"}`];
  if (h.nodriver) parts.push("Nodriver (CLI · open only)");
  $("health").textContent = parts.join(" · ");
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

function setWebSocketIndicator(mode) {
  const el = $("ws-status");
  if (!el) return;
  if (mode === "open") {
    el.textContent = "Log · connected";
    el.className = "muted header-ws-status ws-live";
  } else if (mode === "connecting") {
    el.textContent = "Log · connecting…";
    el.className = "muted header-ws-status";
  } else {
    el.textContent = "Log · reconnecting…";
    el.className = "muted header-ws-status ws-reconnect";
  }
}

let wsBackoffMs = 1000;
let wsReconnectTimer = null;
let wsGen = 0;

function scheduleWebSocketReconnect() {
  if (wsReconnectTimer != null) return;
  const delay = Math.min(wsBackoffMs, 30000);
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    connectWebSocket();
  }, delay);
  wsBackoffMs = Math.min(wsBackoffMs * 2, 30000);
}

function connectWebSocket() {
  const myGen = ++wsGen;
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  setWebSocketIndicator("connecting");
  const socket = new WebSocket(`${proto}//${location.host}/ws/logs`);
  if (ws && ws !== socket) {
    try {
      ws.onclose = null;
      ws.close();
    } catch (_) {}
  }
  ws = socket;
  ws.onopen = () => {
    if (myGen !== wsGen) return;
    wsBackoffMs = 1000;
    if (wsReconnectTimer != null) {
      clearTimeout(wsReconnectTimer);
      wsReconnectTimer = null;
    }
    setWebSocketIndicator("open");
  };
  ws.onmessage = (ev) => {
    if (myGen !== wsGen) return;
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
  ws.onerror = () => {
    /* onclose will schedule reconnect */
  };
  ws.onclose = () => {
    if (myGen !== wsGen) return;
    setWebSocketIndicator("reconnect");
    scheduleWebSocketReconnect();
  };
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  const needsSocket = !ws || ws.readyState === WebSocket.CLOSED;
  if (needsSocket) {
    wsBackoffMs = 1000;
    if (wsReconnectTimer != null) {
      clearTimeout(wsReconnectTimer);
      wsReconnectTimer = null;
    }
    connectWebSocket();
  }
});

const STEP_TYPES = [
  "open_url",
  "goto",
  "click",
  "fill",
  "submit_form",
  "delay",
  "scroll",
  "run_scenario",
  "if_present",
  "exit",
];

/** Max nesting depth for if/then branches in the step builder UI. */
const MAX_BRANCH_BUILDER_DEPTH = 6;

function branchSegmentTypes(depth) {
  if (depth >= MAX_BRANCH_BUILDER_DEPTH) {
    return STEP_TYPES.filter((t) => t !== "if_present");
  }
  return STEP_TYPES;
}

function branchSegmentsKey(segments) {
  return segments.join("\u241e");
}

/** Walk builderSteps: [rootIdx] → row; append branchKey/index pairs for nested steps. */
function getBranchStepBySegments(segments) {
  try {
    if (!segments || segments.length === 0) return undefined;
    let cur = builderSteps[segments[0]];
    if (!cur || segments.length === 1) return cur;
    for (let i = 1; i < segments.length; i += 2) {
      const key = segments[i];
      const idx = Number(segments[i + 1]);
      const arr = cur[key];
      if (!Array.isArray(arr) || arr[idx] === undefined) return undefined;
      cur = arr[idx];
    }
    return cur;
  } catch {
    return undefined;
  }
}

function childSegments(ifStepSegments, branchKey, childIdx) {
  return [...ifStepSegments, branchKey, childIdx];
}

function flushIfPresentSubtreeFromDom(ifStepSegments) {
  const step = getBranchStepBySegments(ifStepSegments);
  if (!step || step.action !== "if_present") return;
  for (const bk of ["then_steps", "else_steps"]) {
    const arr = step[bk] || [];
    for (let ci = 0; ci < arr.length; ci++) {
      const cs = childSegments(ifStepSegments, bk, ci);
      const sel = `[data-branch-seg="${CSS.escape(branchSegmentsKey(cs))}"]`;
      const row = document.querySelector(sel);
      if (row) {
        syncBranchStepRowIntoModel(cs, row);
      }
    }
  }
}

/** Sync every if_present subtree deepest-first so nested rows update parent models before outer rows read them. */
function flushAllIfPresentDomState() {
  const paths = collectIfPresentSegmentPaths();
  paths.sort((a, b) => b.length - a.length);
  for (const seg of paths) {
    flushIfPresentSubtreeFromDom(seg);
  }
}

function collectIfPresentSegmentPaths() {
  /** @type {Array<Array<number|string>>} */
  const paths = [];
  builderSteps.forEach((rootStep, ri) => {
    function visit(step, segPath) {
      if (!step || step.action !== "if_present") return;
      paths.push([...segPath]);
      for (const bk of ["then_steps", "else_steps"]) {
        (step[bk] || []).forEach((child, ci) => {
          visit(child, childSegments(segPath, bk, ci));
        });
      }
    }
    visit(rootStep, [ri]);
  });
  return paths;
}

function flushEveryIfPresentSubtreeFromDom() {
  flushAllIfPresentDomState();
}

function syncBranchStepRowIntoModel(segments, rowEl) {
  const prev = getBranchStepBySegments(segments);
  if (!prev) return;
  const action =
    rowEl.querySelector(':scope > .nested-branch-toolbar [data-field="action"]')?.value ||
    prev.action;
  const scoped = rowEl.querySelector(".nested-branch-step-fields");
  if (!scoped) return;
  const step = { action };
  scoped.querySelectorAll("[data-field]").forEach((el) => {
    const key = el.dataset.field;
    if (!key || key === "action") return;
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
  if (action === "if_present") {
    step.then_steps = Array.isArray(prev.then_steps) ? prev.then_steps : [];
    step.else_steps = Array.isArray(prev.else_steps) ? prev.else_steps : [];
  }
  replaceBranchStepAtSegments(segments, normalizeStep(step));
}

function replaceBranchStepAtSegments(segments, normalizedStep) {
  if (!segments || segments.length < 3) return;
  const branchKey = segments[segments.length - 2];
  const leafIdx = Number(segments[segments.length - 1]);
  let parentArr;
  if (segments.length === 3) {
    const rootIdx = segments[0];
    parentArr = builderSteps[rootIdx]?.[branchKey];
  } else {
    const parentSeg = segments.slice(0, -2);
    const ps = getBranchStepBySegments(parentSeg);
    parentArr = ps?.[branchKey];
  }
  if (!Array.isArray(parentArr) || !parentArr[leafIdx]) return;
  parentArr[leafIdx] = normalizedStep;
}

function changeNestedBranchStepType(segments, newAction) {
  const cur = getBranchStepBySegments(segments);
  if (!cur || cur.action === newAction) return;
  replaceBranchStepAtSegments(segments, normalizeStep(defaultStep(newAction)));
  renderSteps();
}

function attachBranchStepScopedListeners(rowEl, segments) {
  const syncThis = () => {
    syncBranchStepRowIntoModel(segments, rowEl);
    syncUnsavedIndicators();
  };
  rowEl.querySelectorAll("input, select, textarea").forEach((inp) => {
    inp.addEventListener("change", syncThis);
    inp.addEventListener("input", syncThis);
  });
}

function renderFormFieldBranchRow(segments, fieldIndex, field) {
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
      syncUnsavedIndicators();
    });
    addCol("Find by", bySel, locGrid, "locator.by");

    for (const [key, label, type, , helpId] of locatorFieldDefs(by)) {
      const inp = fieldInput(key, field[key] || "", type);
      inp.addEventListener("input", () => {
        field[key] = inp.value;
        syncUnsavedIndicators();
      });
      addCol(label, inp, locGrid, helpId);
    }

    const valueInp = fieldInput("value", field.value || "");
    valueInp.addEventListener("input", () => {
      field.value = valueInp.value;
      syncUnsavedIndicators();
    });
    addCol("Value", valueInp, locGrid, "locator.value");
  };

  renderFieldInputs();
  wrap.appendChild(locGrid);

  const host = () => getBranchStepBySegments(segments);
  const del =
    typeof makeIconButton === "function"
      ? makeIconButton(
          "trash",
          "Remove field",
          (e) => {
            e.stopPropagation();
            const h = host();
            if (h?.fields) h.fields.splice(fieldIndex, 1);
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
            const h = host();
            if (h?.fields) h.fields.splice(fieldIndex, 1);
            renderSteps();
          };
          return b;
        })();
  del.classList.add("btn-remove-field");
  wrap.appendChild(del);
  return wrap;
}

function targetStepForPlacement(placement) {
  if (placement.type === "main") return builderSteps[placement.index];
  return getBranchStepBySegments(placement.segments);
}

function getSiblingStepsArrayRef(placement) {
  if (placement.type === "main") return builderSteps;
  const segs = placement.segments;
  if (!segs || segs.length < 3) return null;
  const host = getBranchStepBySegments(segs.slice(0, -2));
  const bk = segs[segs.length - 2];
  if (!host || !bk) return null;
  const arr = host[bk];
  return Array.isArray(arr) ? arr : null;
}

/** Index of this step inside its sibling list (main flow row index or nested branch leaf index). */
function siblingIndexFromPlacement(placement) {
  if (placement.type === "main") return placement.index;
  const segs = placement.segments;
  return Number(segs[segs.length - 1]);
}

/** Non-empty workflow_label values on sibling steps strictly after siblingIndex (valid goto targets). */
function forwardWorkflowLabelTargets(placement, siblingIndex) {
  const arr = getSiblingStepsArrayRef(placement);
  if (!Array.isArray(arr)) return [];
  const out = [];
  for (let j = siblingIndex + 1; j < arr.length; j++) {
    const wl =
      typeof arr[j].workflow_label === "string" ? arr[j].workflow_label.trim() : "";
    if (wl) out.push(wl);
  }
  return [...new Set(out)].sort();
}

function trimmedWorkflowLabel(step) {
  return typeof step.workflow_label === "string" ? step.workflow_label.trim() : "";
}

/** Icon-only control beside delete when step label is hidden (empty + not expanded). */
function appendCollapsedWorkflowLabelTrigger(container, step) {
  if (!step) return;
  const wl = trimmedWorkflowLabel(step);
  if (wl !== "" || workflowLabelUiExpandedByStepRef.get(step) === true) return;

  const reveal = (e) => {
    e.stopPropagation();
    workflowLabelUiExpandedByStepRef.set(step, true);
    renderSteps();
  };

  if (typeof makeIconButton === "function") {
    const btn = makeIconButton("tag", "Add step label", reveal);
    btn.classList.add("outline");
    container.appendChild(btn);
    return;
  }

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "outline";
  btn.textContent = "#";
  btn.title = "Add step label";
  btn.setAttribute("aria-label", "Add step label");
  btn.addEventListener("click", reveal);
  container.appendChild(btn);
}

/** Optional workflow label: field appears once expanded or when a label exists (collapse trigger lives in row toolbar). */
function appendWorkflowLabelField(fields, step) {
  const wl = trimmedWorkflowLabel(step);
  const expandedEmptySession = workflowLabelUiExpandedByStepRef.get(step) === true;
  const showField = wl !== "" || expandedEmptySession;

  if (!showField) return;

  const row = document.createElement("div");
  row.className = "workflow-label-row";

  const fieldCol = document.createElement("div");
  fieldCol.className = "workflow-label-field-col";
  fieldCol.appendChild(
    labeledField(
      "workflow_label",
      "Step label",
      step.workflow_label || "",
      "text",
      "Optional anchor for workflow goto (unique among steps in this list)",
      "scenario.workflow_label"
    )
  );
  row.appendChild(fieldCol);

  if (expandedEmptySession && !wl) {
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "workflow-label-secondary-btn outline";
    cancel.textContent = "Cancel";
    cancel.title = "Hide step label field";
    cancel.addEventListener("click", (e) => {
      e.stopPropagation();
      workflowLabelUiExpandedByStepRef.delete(step);
      renderSteps();
    });
    row.appendChild(cancel);
  } else if (wl) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "workflow-label-secondary-btn outline danger";
    remove.textContent = "Remove";
    remove.title = "Clear step label";
    remove.addEventListener("click", (e) => {
      e.stopPropagation();
      flushBuilderFromDom();
      step.workflow_label = "";
      workflowLabelUiExpandedByStepRef.delete(step);
      renderSteps();
    });
    row.appendChild(remove);
  }

  fields.appendChild(row);
}

/**
 * All step field UIs except if_present branch arms (handled separately).
 * @param {{ type: "main", index: number } | { type: "branch", segments: (string|number)[] }} placement
 */
function appendStepFieldsNotIfPresent(fields, step, placement) {
  const locCtx = placement.type === "main" ? placement.index : placement.segments;
  const curName = $("build-name").value.trim();
  const sibIx = siblingIndexFromPlacement(placement);

  appendWorkflowLabelField(fields, step);

  if (step.action === "open_url") {
    fields.appendChild(labeledField("url", "URL", step.url || "", "url", "", "step.open_url.url"));
  } else if (step.action === "goto") {
    const fwd = forwardWorkflowLabelTargets(placement, sibIx);
    const val = typeof step.goto_label === "string" ? step.goto_label.trim() : "";
    if (fwd.length) {
      const mergedOpts = [...new Set([...fwd, val].filter(Boolean))].sort();
      fields.appendChild(
        labeledSelect(
          "goto_label",
          "Jump to label",
          val || mergedOpts[0],
          mergedOpts,
          "Forward-only: must match a later step’s Step label in this list.",
          "step.goto.target"
        )
      );
    } else {
      fields.appendChild(
        labeledField(
          "goto_label",
          "Jump to label",
          val,
          "text",
          "Set Step label on later steps first, then pick the target.",
          "step.goto.target"
        )
      );
    }
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
    appendLocatorFields(fields, step, false, locCtx);
  } else if (step.action === "fill") {
    if (!step.by) step.by = "css";
    appendLocatorFields(fields, step, true, locCtx);
  } else if (step.action === "run_scenario") {
    const opts = scenarios
      .filter((s) => (s.type === "json" || s.type === "python") && s.name !== curName)
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
  } else if (step.action === "exit") {
    fields.appendChild(
      labeledField("message", "Log message (optional)", step.message || "", "text", "", "step.exit.message")
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
      if (placement.type === "main") {
        fieldsWrap.appendChild(renderFormFieldRow(placement.index, fi, f));
      } else {
        fieldsWrap.appendChild(renderFormFieldBranchRow(placement.segments, fi, f));
      }
    });
    fields.appendChild(fieldsWrap);

    const addField = document.createElement("button");
    addField.type = "button";
    addField.className = "btn-add-field success outline";
    addField.onclick = (e) => {
      e.stopPropagation();
      const hostStep = targetStepForPlacement(placement);
      if (!hostStep.fields) hostStep.fields = [];
      hostStep.fields.push({ by: "css", selector: "", value: "" });
      renderSteps();
    };
    if (typeof enhanceButton === "function") {
      enhanceButton(addField, "plus", { label: "Add field" });
    } else {
      addField.textContent = "+ field";
    }
    fields.appendChild(addField);
  } else if (step.action === "if_present") {
    if (!step.by) step.by = "role";
    appendLocatorFields(fields, step, false, locCtx);
    fields.appendChild(
      labeledField(
        "timeout_ms",
        "Visible timeout (ms)",
        step.timeout_ms ?? 3000,
        "number",
        "How long to wait for a visible match; 0 checks immediately",
        "step.if_present.timeout"
      )
    );
  }
}

/** @param nestingDepth Depth of the parent if_present step (0 = root flow step's if_present). */
function renderBranchStepsSection(ifParentSegments, branchKey, branchTitle, nestingDepth) {
  const wrap = document.createElement("div");
  wrap.className = "nested-branch-arm";
  const hdr = document.createElement("div");
  hdr.className = "nested-branch-arm-header";
  const lab = document.createElement("span");
  lab.className = "field-label";
  lab.textContent = branchTitle;
  hdr.appendChild(lab);
  wrap.appendChild(hdr);

  const list = document.createElement("div");
  list.className = "nested-branch-steps-list";
  const host = getBranchStepBySegments(ifParentSegments);
  const arr = (host && Array.isArray(host[branchKey]) ? host[branchKey] : []) || [];
  arr.forEach((_st, ci) => {
    list.appendChild(renderNestedBranchStepRow(childSegments(ifParentSegments, branchKey, ci), nestingDepth + 1));
  });
  wrap.appendChild(list);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "btn-add-nested-step success outline";
  addBtn.textContent = "Add step";
  addBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    flushAllIfPresentDomState();
    const p = getBranchStepBySegments(ifParentSegments);
    if (!p || !Array.isArray(p[branchKey])) return;
    p[branchKey].push(normalizeStep(defaultStep("open_url")));
    renderSteps();
  });
  wrap.appendChild(addBtn);
  return wrap;
}

/** @param ifNestingDepth 1-based depth of this row under branch arms (1 = direct child of root if_present's Then/Else). */
function renderNestedBranchStepRow(segments, ifNestingDepth) {
  const step = getBranchStepBySegments(segments);
  const row = document.createElement("div");
  row.className = "nested-branch-step";
  row.dataset.branchSeg = branchSegmentsKey(segments);

  const toolbar = document.createElement("div");
  toolbar.className = "nested-branch-toolbar";

  const typeWrap = document.createElement("div");
  typeWrap.className = "field-labeled nested-branch-type-wrap";
  const typeLabRow = document.createElement("div");
  typeLabRow.className = "label-row";
  const typeLab = document.createElement("span");
  typeLab.className = "field-label";
  typeLab.textContent = "Step";
  typeLabRow.appendChild(typeLab);
  typeWrap.appendChild(typeLabRow);
  const typeSelect = document.createElement("select");
  typeSelect.className = "step-type-select nested-branch-action";
  typeSelect.dataset.field = "action";
  branchSegmentTypes(ifNestingDepth).forEach((t) => {
    const o = document.createElement("option");
    o.value = t;
    o.textContent = t;
    if (step?.action === t) o.selected = true;
    typeSelect.appendChild(o);
  });
  typeSelect.addEventListener("change", () =>
    changeNestedBranchStepType(segments, typeSelect.value)
  );
  typeWrap.appendChild(typeSelect);
  toolbar.appendChild(typeWrap);

  const toolbarActions = document.createElement("div");
  toolbarActions.className = "nested-branch-toolbar-actions";
  appendCollapsedWorkflowLabelTrigger(toolbarActions, step);

  if (typeof makeIconButton === "function") {
    toolbarActions.appendChild(
      makeIconButton(
        "trash",
        "Remove step",
        (e) => {
          e.stopPropagation();
          removeNestedBranchLeafStep(segments);
        },
        { danger: true }
      )
    );
  } else {
    const del = document.createElement("button");
    del.type = "button";
    del.className = "danger";
    del.textContent = "×";
    del.title = "Remove step";
    del.onclick = (e) => {
      e.stopPropagation();
      removeNestedBranchLeafStep(segments);
    };
    toolbarActions.appendChild(del);
  }
  toolbar.appendChild(toolbarActions);
  row.appendChild(toolbar);

  const placement = /** @type {const} */ ({ type: "branch", segments });

  const fields = document.createElement("div");
  fields.className = "nested-branch-step-fields";

  let armsEl = null;
  if (step && step.action === "if_present") {
    appendStepFieldsNotIfPresent(fields, step, placement);
    armsEl = document.createElement("div");
    armsEl.className = "nested-branch-arms";
    armsEl.appendChild(
      renderBranchStepsSection(segments, "then_steps", "Then (if matched)", ifNestingDepth)
    );
    armsEl.appendChild(
      renderBranchStepsSection(segments, "else_steps", "Else (not matched)", ifNestingDepth)
    );
  } else {
    appendStepFieldsNotIfPresent(fields, step ?? normalizeStep(defaultStep("open_url")), placement);
  }

  row.appendChild(fields);
  if (armsEl) row.appendChild(armsEl);
  attachBranchStepScopedListeners(row, segments);
  return row;
}

function removeNestedBranchLeafStep(segments) {
  if (!segments || segments.length < 3) return;
  flushAllIfPresentDomState();
  const branchKey = segments[segments.length - 2];
  const ix = Number(segments[segments.length - 1]);
  let arr;
  if (segments.length === 3) {
    const rootIx = segments[0];
    arr = builderSteps[rootIx]?.[branchKey];
  } else {
    const parentSeg = segments.slice(0, -2);
    const parent = getBranchStepBySegments(parentSeg);
    arr = parent?.[branchKey];
  }
  if (!Array.isArray(arr)) return;
  arr.splice(ix, 1);
  renderSteps();
}

function changeStepType(index, newAction) {
  if (builderSteps[index].action === newAction) return;
  builderSteps[index] = defaultStep(newAction);
  renderSteps();
}

function defaultStep(action) {
  switch (action) {
    case "open_url":
      return { action: "open_url", url: $("build-url").value || "https://example.com" };
    case "goto":
      return { action: "goto", goto_label: "later_step", workflow_label: "" };
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
    case "if_present":
      return {
        action: "if_present",
        by: "role",
        role: "button",
        name: "",
        timeout_ms: 3000,
        then_steps: [],
        else_steps: [],
      };
    case "exit":
      return { action: "exit", message: "" };
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
  const glRaw = typeof s.goto_label === "string" ? s.goto_label.trim() : "";
  if (
    s.action === "goto" &&
    !glRaw &&
    typeof s.url === "string" &&
    s.url.trim() !== ""
  ) {
    s.action = "open_url";
    delete s.goto_label;
  }
  if (typeof s.workflow_label !== "string") s.workflow_label = "";
  if (s.action === "open_url") {
    if (typeof s.url !== "string") s.url = "";
  }
  if (s.action === "goto") {
    if (typeof s.goto_label !== "string") s.goto_label = "";
  }
  if (s.action === "submit_form" && Array.isArray(s.fields)) {
    s.fields = s.fields.map((f) => normalizeLocatorFields({ ...f }));
  }
  if (s.action === "run_scenario") {
    s.inherit_delays = !!s.inherit_delays;
    s.skip_start_url = s.skip_start_url !== false;
    if (typeof s.scenario !== "string") s.scenario = "";
  }
  if (s.action === "if_present") {
    if (typeof s.timeout_ms !== "number" || Number.isNaN(s.timeout_ms)) s.timeout_ms = 3000;
    if (!Array.isArray(s.then_steps)) s.then_steps = [];
    if (!Array.isArray(s.else_steps)) s.else_steps = [];
  }
  if (s.action === "exit" && typeof s.message !== "string") s.message = "";
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

function appendLocatorFields(container, step, includeValue, stepIndexOrSegments) {
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
    if (typeof stepIndexOrSegments === "number") {
      const row = document.querySelector(`[data-step-index="${stepIndexOrSegments}"]`);
      if (row) syncStepFromDom(stepIndexOrSegments, row);
      builderSteps[stepIndexOrSegments].by = e.target.value;
    } else {
      step.by = e.target.value;
    }
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
      syncUnsavedIndicators();
    });
    addCol("Find by", bySel, locGrid, "locator.by");

    for (const [key, label, type, , helpId] of locatorFieldDefs(by)) {
      const inp = fieldInput(key, field[key] || "", type);
      inp.addEventListener("input", () => {
        field[key] = inp.value;
        syncUnsavedIndicators();
      });
      addCol(label, inp, locGrid, helpId);
    }

    const valueInp = fieldInput("value", field.value || "");
    valueInp.addEventListener("input", () => {
      field.value = valueInp.value;
      syncUnsavedIndicators();
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

  const placementMain = /** @type {const} */ ({ type: "main", index });
  let branchArmsRoot = null;

  if (step.action === "if_present") {
    appendStepFieldsNotIfPresent(fields, step, placementMain);
    branchArmsRoot = document.createElement("div");
    branchArmsRoot.className = "nested-branch-arms nested-branch-arms-root";
    branchArmsRoot.appendChild(renderBranchStepsSection([index], "then_steps", "Then (if matched)", 0));
    branchArmsRoot.appendChild(renderBranchStepsSection([index], "else_steps", "Else (not matched)", 0));
  } else {
    appendStepFieldsNotIfPresent(fields, step, placementMain);
  }

  row.appendChild(fields);
  if (branchArmsRoot) row.appendChild(branchArmsRoot);

  const actions = document.createElement("div");
  actions.className = "step-actions";
  appendCollapsedWorkflowLabelTrigger(actions, step);
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

  fields.querySelectorAll("input, select, textarea").forEach((inp) => {
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

/** Apply root step row DOM into `builderSteps` without updating unsaved indicators. */
function applyStepFromDom(index, row) {
  const prev = builderSteps[index];
  const action =
    row.querySelector('[data-field="action"]')?.value || prev.action;
  const step = { action };
  row.querySelectorAll("[data-field]").forEach((el) => {
    if (el.closest(".nested-branch-arms")) return;
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
  if (action === "if_present") {
    step.then_steps = Array.isArray(prev.then_steps) ? prev.then_steps : [];
    step.else_steps = Array.isArray(prev.else_steps) ? prev.else_steps : [];
  }
  builderSteps[index] = normalizeStep(step);
}

function syncStepFromDom(index, row) {
  applyStepFromDom(index, row);
  syncUnsavedIndicators();
}

function flushBuilderFromDom() {
  flushAllIfPresentDomState();
  builderSteps.forEach((_, i) => {
    const row = document.querySelector(`[data-step-index="${i}"]`);
    if (row) applyStepFromDom(i, row);
  });
}

function renderSteps() {
  const list = $("steps-list");
  list.innerHTML = "";
  builderSteps.forEach((step, i) => list.appendChild(renderStepRow(step, i)));
  initStepDragDrop(list);
  syncUnsavedIndicators();
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
  container.querySelectorAll("[data-scenario-field]").forEach((el) => {
    el.addEventListener("input", syncUnsavedIndicators);
    el.addEventListener("change", syncUnsavedIndicators);
  });
}

function collectDocument() {
  flushBuilderFromDom();
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
  const previousStem =
    !isDraftSelected() && selectedScenario && selectedScenario !== DRAFT_SCENARIO_ID
      ? selectedScenario
      : null;
  /** @type {Record<string, string>} */
  const headers = {};
  if (previousStem && previousStem !== name) {
    headers["X-Rename-From"] = previousStem;
  }
  await api(`/api/scenarios/${encodeURIComponent(name)}/python-source`, {
    method: "PUT",
    headers,
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
  const previousStem =
    !isDraftSelected() && selectedScenario && selectedScenario !== DRAFT_SCENARIO_ID
      ? selectedScenario
      : null;
  /** @type {Record<string, string>} */
  const headers = {};
  if (previousStem && previousStem !== doc.name.trim()) {
    headers["X-Rename-From"] = previousStem;
  }
  await api("/api/scenarios", { method: "POST", headers, body: JSON.stringify(doc) });
  const wasDraft = isDraftSelected();
  $("build-msg").textContent = `Saved "${doc.name}"`;
  selectedScenario = doc.name;
  await loadScenarios();
  if (wasDraft) {
    renderScenarioList("scenario-list", scenarioListOnSelect);
  }
  setSelectedScenario(doc.name);
}


async function duplicateCurrentFlow() {
  if (isDraftSelected() || !selectedScenario) {
    showError("Save and select a flow before duplicating.");
    return;
  }
  const info = getScenarioInfo(selectedScenario);
  if (!info) return;
  const newName = uniqueScenarioName(`${selectedScenario}_copy`);
  try {
    if (info.type === "python") {
      const payload = await api(`/api/scenarios/${encodeURIComponent(selectedScenario)}/python-source`);
      await api(`/api/scenarios/${encodeURIComponent(newName)}/python-source`, {
        method: "PUT",
        body: JSON.stringify({ source: payload.source }),
      });
    } else {
      const doc = await api(`/api/scenarios/${encodeURIComponent(selectedScenario)}`);
      doc.name = newName;
      await api("/api/scenarios", { method: "POST", body: JSON.stringify(doc) });
    }
    await loadScenarios();
    await selectScenario(newName);
    showSuccess(`Duplicated as "${newName}".`);
  } catch (e) {
    showError(e.message);
  }
}

function exportCurrentJsonFlow() {
  try {
    const doc = collectDocument();
    if (!doc.name) {
      showError("Set a flow name before exporting.");
      return;
    }
    downloadText(`${doc.name}.json`, JSON.stringify(doc, null, 2), "application/json;charset=utf-8");
  } catch (e) {
    showError(e.message);
  }
}

function exportCurrentPythonFlow() {
  const name = $("build-name")?.value.trim();
  if (!name) {
    showError("Set a flow name before exporting.");
    return;
  }
  downloadText(`${name}.py`, getPythonSource(), "text/x-python;charset=utf-8");
}

async function applyImportedJson(text, suggestedName) {
  let raw;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new Error("File is not valid JSON.");
  }
  const doc = normalizeImportedJsonDoc(raw);
  const stem = (suggestedName && String(suggestedName).replace(/\.json$/i, "").trim()) || "";
  if (stem && stem !== doc.name) doc.name = stem;
  doc.name = uniqueScenarioName(doc.name);
  draftIsPython = false;
  setSelectedScenario(DRAFT_SCENARIO_ID, { skipPreview: true });
  showJsonFlowEditor();
  populateFlowEditor(doc);
  renderScenarioList("scenario-list", scenarioListOnSelect);
  syncScenarioListSelection();
  $("build-msg").textContent = `Imported draft "${doc.name}" — review and save.`;
  updateDeleteFlowButton();
  clearRunStepProgress();
  commitSavedBaseline();
}

async function applyImportedPython(text, suggestedName) {
  const stem = (suggestedName && String(suggestedName).replace(/\.py$/i, "").trim()) || "imported_flow";
  const name = uniqueScenarioName(stem);
  draftIsPython = true;
  setSelectedScenario(DRAFT_SCENARIO_ID, { skipPreview: true });
  setPythonSource(text);
  $("build-name").value = name;
  showPythonFlowEditor();
  refreshPythonEditorLayout();
  renderScenarioList("scenario-list", scenarioListOnSelect);
  syncScenarioListSelection();
  $("build-msg-python").textContent = `Imported draft "${name}" — review and save.`;
  updateDeleteFlowButton();
  clearRunStepProgress();
  commitSavedBaseline();
}

function onFlowImportFileSelected(ev) {
  const input = ev.target;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  void (async () => {
    if (!(await maybeConfirmDiscardForImport())) return;
    const reader = new FileReader();
    reader.onload = () => {
      void (async () => {
        try {
          const text = String(reader.result || "");
          const fname = file.name || "";
          if (importTargetKind === "python") {
            if (/\.json$/i.test(fname) || /^\s*\{/.test(text)) {
              try {
                await applyImportedJson(text, fname);
                return;
              } catch {
                /* fall through as Python source */
              }
            }
            await applyImportedPython(text, fname);
            return;
          }
          const looksPy =
            /\.py$/i.test(fname) ||
            (/async\s+def\s+run\s*\(/.test(text) && !/^\s*\{/.test(text));
          if (looksPy) {
            await applyImportedPython(text, fname);
            return;
          }
          await applyImportedJson(text, fname);
        } catch (e) {
          showError(e.message);
        }
      })();
    };
    reader.readAsText(file);
  })();
}

async function startRun(scenarioName) {
  const scenario = scenarioName || getSelectedScenario();
  if (!scenario) return;
  const pw = getRunPlaywrightOptions();
  const body = {
    scenario,
    loops: parseInt($("run-loops").value, 10) || 1,
    pause_between_loops_sec: parseFloat($("run-pause").value) || 0,
    headless: $("run-headless").checked,
    ignore_https_errors: $("run-ignore-https-errors")?.checked ?? false,
    channel: pw.channel,
    slow_mo: pw.slow_mo,
    keep_session_open: $("run-keep-session-open")?.checked ?? false,
  };
  try {
    await api("/api/run", { method: "POST", body: JSON.stringify(body) });
  } catch (e) {
    const msg =
      e.status === 409
        ? "A run is already in progress. Stop it or wait for it to finish."
        : e.message;
    showError(msg);
    return;
  }
  $("log-output").textContent = "";
  await initRunStepProgress(scenario);
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

function closeGroupsAddDropdowns() {
  document.querySelectorAll("#panel-groups .groups-add-dropdown[open]").forEach((d) => {
    d.open = false;
  });
}

function editableScenarioNamesList() {
  return scenarios.filter((s) => s.type === "json" || s.type === "python").map((s) => s.name);
}

/** Names not yet in this group's scenario_names (sorted). */
function availableFlowsForGroup(groupIndex) {
  const all = editableScenarioNamesList();
  const have = new Set(groupsModalDraft[groupIndex]?.scenario_names || []);
  return all.filter((n) => !have.has(n)).sort((a, b) => a.localeCompare(b));
}

function addFlowToGroup(groupIndex, flowName) {
  const g = groupsModalDraft[groupIndex];
  if (!g) return;
  const arr = g.scenario_names || [];
  if (!arr.includes(flowName)) arr.push(flowName);
  g.scenario_names = arr;
  renderGroupsModalEditor();
}

function removeFlowFromGroup(groupIndex, flowName) {
  const g = groupsModalDraft[groupIndex];
  if (!g) return;
  g.scenario_names = (g.scenario_names || []).filter((n) => n !== flowName);
  renderGroupsModalEditor();
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

    const header = document.createElement("div");
    header.className = "groups-modal-card-header";

    const title = document.createElement("h3");
    title.className = "groups-modal-card-title";
    title.textContent = (g.id || "").trim() || "Group";
    title.setAttribute("title", `Group id: ${(g.id || "").trim() || "—"}`);

    header.appendChild(title);
    row.appendChild(header);

    const labLab = document.createElement("label");
    labLab.className = "field-label";
    labLab.textContent = "Label";
    const labInp = document.createElement("input");
    labInp.type = "text";
    labInp.value = g.label || "";
    labInp.addEventListener("input", () => {
      groupsModalDraft[gi].label = labInp.value.trim();
    });

    const flowsSection = document.createElement("div");
    flowsSection.className = "groups-flows-section";

    const flowsHeading = document.createElement("span");
    flowsHeading.className = "field-label groups-flows-heading";
    flowsHeading.textContent = "Flows in group";

    const memberList = document.createElement("ul");
    memberList.className = "groups-flow-members";
    memberList.setAttribute("aria-label", "Flows in this group");

    const members = g.scenario_names || [];
    if (members.length === 0) {
      const emptyLi = document.createElement("li");
      emptyLi.className = "groups-flow-members-empty muted";
      emptyLi.textContent = "No flows in this group yet.";
      memberList.appendChild(emptyLi);
    } else {
      members.forEach((nm) => {
        const li = document.createElement("li");
        li.className = "groups-flow-member";

        const nameWrap = document.createElement("div");
        nameWrap.className = "groups-flow-member-main";

        const span = document.createElement("span");
        span.className = "groups-flow-member-name";
        span.textContent = nm;

        const info = scenarios.find((s) => s.name === nm);
        const typeTag = document.createElement("span");
        typeTag.className =
          info?.type === "python"
            ? "groups-flow-member-badge badge-python"
            : "groups-flow-member-badge badge-json";
        typeTag.textContent = info?.type === "python" ? "python" : "json";

        nameWrap.appendChild(span);
        nameWrap.appendChild(typeTag);

        const rm = document.createElement("button");
        rm.type = "button";
        rm.className = "danger outline groups-flow-remove";
        rm.textContent = "Remove";
        rm.addEventListener("click", () => removeFlowFromGroup(gi, nm));

        li.appendChild(nameWrap);
        li.appendChild(rm);
        memberList.appendChild(li);
      });
    }

    const avail = availableFlowsForGroup(gi);
    const addWrap = document.createElement("div");
    addWrap.className = "groups-add-flow-wrap";

    const details = document.createElement("details");
    details.className = "groups-add-dropdown";

    const summary = document.createElement("summary");
    summary.className = "groups-add-summary outline success btn-with-icon";
    summary.setAttribute("aria-haspopup", "menu");
    summary.appendChild(icon("plus"));
    const addFlowLabel = document.createElement("span");
    addFlowLabel.className = "btn-label";
    addFlowLabel.textContent = "Add flow";
    summary.appendChild(addFlowLabel);

    const panel = document.createElement("div");
    panel.className = "groups-add-panel";
    panel.setAttribute("role", "menu");
    panel.setAttribute("aria-label", "Flows not in this group");

    if (avail.length === 0) {
      const hint = document.createElement("p");
      hint.className = "muted groups-add-empty";
      hint.textContent =
        editableScenarioNamesList().length === 0
          ? "No saved flows yet. Create flows in Workspace first."
          : "Every saved flow is already in this group.";
      panel.appendChild(hint);
    } else {
      avail.forEach((nm) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "groups-add-option";
        btn.setAttribute("role", "menuitem");
        const info = scenarios.find((s) => s.name === nm);
        btn.textContent =
          nm +
          (info?.type === "python" ? " · python" : info?.type === "json" ? " · json" : "");
        btn.addEventListener("click", () => {
          addFlowToGroup(gi, nm);
          details.open = false;
          closeGroupsAddDropdowns();
        });
        panel.appendChild(btn);
      });
    }

    details.appendChild(summary);
    details.appendChild(panel);
    addWrap.appendChild(details);

    flowsSection.appendChild(flowsHeading);
    flowsSection.appendChild(memberList);

    const cardActions = document.createElement("div");
    cardActions.className = "groups-card-actions";

    const del = document.createElement("button");
    del.type = "button";
    del.className = "danger outline";
    del.addEventListener("click", () => {
      groupsModalDraft.splice(gi, 1);
      renderGroupsModalEditor();
    });
    enhanceButton(del, "trash", { label: "Remove group" });

    cardActions.appendChild(addWrap);
    cardActions.appendChild(del);
    flowsSection.appendChild(cardActions);

    row.appendChild(labLab);
    row.appendChild(labInp);
    row.appendChild(flowsSection);
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
  closeGroupsAddDropdowns();
  groupsModalDraft = structuredClone(groupsData.groups || []);
  renderGroupsModalEditor();
  setMainTab("groups");
}

async function saveGroupsModal() {
  $("groups-msg").textContent = "";
  closeGroupsAddDropdowns();
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
  const pw = getRunPlaywrightOptions();
  const body = {
    group_id: groupId,
    loops: parseInt($("run-loops").value, 10) || 1,
    pause_between_loops_sec: parseFloat($("run-pause").value) || 0,
    pause_between_flows_sec: parseFloat($("run-pause-flows")?.value || "0") || 0,
    headless: $("run-headless").checked,
    ignore_https_errors: $("run-ignore-https-errors")?.checked ?? false,
    channel: pw.channel,
    slow_mo: pw.slow_mo,
    keep_session_open: $("run-keep-session-open")?.checked ?? false,
  };
  try {
    await api("/api/run/group", { method: "POST", body: JSON.stringify(body) });
  } catch (e) {
    const msg =
      e.status === 409
        ? "A run is already in progress. Stop it or wait for it to finish."
        : e.message;
    showError(msg);
    return;
  }
  $("log-output").textContent = "";
  await initRunStepProgress(`group:${groupId}`);
  startRunStatusPolling();
  try {
    await refreshRunStepProgressFromServer();
  } catch {
    /* polling / websocket will catch up */
  }
}

$("btn-start").onclick = () => startRun().catch((e) => showError(e.message));
$("btn-stop").onclick = () =>
  api("/api/run/stop", { method: "POST" }).catch((e) => showError(e.message));
$("tab-workspace")?.addEventListener("click", () => setMainTab("workspace"));
$("tab-groups")?.addEventListener("click", () => openGroupsPanel());
$("groups-save")?.addEventListener("click", () =>
  saveGroupsModal().catch((e) => {
    $("groups-msg").textContent = e.message;
    showError(e.message);
  })
);
$("groups-back")?.addEventListener("click", () => setMainTab("workspace"));
$("btn-add-step").onclick = () => {
  const last = builderSteps[builderSteps.length - 1];
  builderSteps.push(defaultStep(last?.action || "open_url"));
  renderSteps();
};
$("btn-save").onclick = () =>
  saveScenario().catch((e) => {
    $("build-msg").textContent = e.message;
    showError(e.message);
  });
$("btn-new-flow")?.addEventListener("click", () =>
  createNewFlowFromToolbar().catch((e) => showError(e.message))
);
$("btn-save-python")?.addEventListener("click", () =>
  savePythonScenario().catch((e) => {
    $("build-msg-python").textContent = e.message;
    showError(e.message);
  })
);
document.querySelectorAll(".btn-delete-flow").forEach((btn) => {
  btn.addEventListener("click", () =>
    deleteSelectedFlow().catch((e) => {
      const jsonEditorVisible = !$("flow-editor-wrap")?.classList.contains("hidden");
      $(jsonEditorVisible ? "build-msg" : "build-msg-python").textContent = e.message;
      showError(e.message);
    })
  );
});
$("btn-dup-json")?.addEventListener("click", () => duplicateCurrentFlow());
$("btn-export-json")?.addEventListener("click", () => exportCurrentJsonFlow());
$("btn-import-json")?.addEventListener("click", () => {
  importTargetKind = "json";
  $("flow-import-input")?.click();
});
$("btn-dup-python")?.addEventListener("click", () => duplicateCurrentFlow());
$("btn-export-python")?.addEventListener("click", () => exportCurrentPythonFlow());
$("btn-import-python")?.addEventListener("click", () => {
  importTargetKind = "python";
  $("flow-import-input")?.click();
});
$("flow-import-input")?.addEventListener("change", onFlowImportFileSelected);
$("btn-test-run").onclick = async () => {
  try {
    await saveScenario();
    await startRun($("build-name").value.trim());
  } catch (e) {
    $("build-msg").textContent = e.message;
    showError(e.message);
  }
};
$("btn-test-run-python")?.addEventListener("click", async () => {
  try {
    await savePythonScenario();
    await startRun($("build-name").value.trim());
  } catch (e) {
    $("build-msg-python").textContent = e.message;
    showError(e.message);
  }
});

(async () => {
  try {
    loadPersistedRunOptions();
    wireRunOptionsPersistence();
    const isLightInit = document.documentElement.getAttribute("data-theme") === "light";
    if ($("btn-theme")) $("btn-theme").textContent = isLightInit ? "Dark" : "Light";
    $("btn-theme")?.addEventListener("click", toggleTheme);

    initPythonCodeMirror();
    await loadHealth();
    await loadScenarios();
    const st = await api("/api/run/status");
    setRunStatus(st);
    updateRunButtons(st.state);
    if (runIsBusy(st.state) && st.scenario) {
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
      await newFlow();
    }
    $("build-random-between-steps").addEventListener("change", () => {
      renderScenarioOptions(readScenarioOptions());
      syncUnsavedIndicators();
    });
    $("build-name")?.addEventListener("input", onBuildNameDescInput);
    $("build-desc")?.addEventListener("input", onBuildNameDescInput);
    $("build-url")?.addEventListener("input", syncUnsavedIndicators);
    $("python-source-editor")?.addEventListener("input", syncUnsavedIndicators);

    $("build-flow-kind")?.addEventListener("change", () => {
      void (async () => {
        const sel = $("build-flow-kind");
        if (!sel) return;
        const wantPython = sel.value === "python";
        if (!isDraftSelected()) return;
        if (wantPython === draftIsPython) return;
        const msg = wantPython
          ? "Switch this draft to a Python flow? The JSON step builder will be replaced by the Python template."
          : "Switch this draft to JSON? The Python editor will reset to the JSON step builder with an open_url step.";
        if (!(await showConfirmAsync(msg))) {
          sel.value = draftIsPython ? "python" : "json";
          return;
        }
        if (wantPython) {
          draftIsPython = true;
          setPythonSource(PYTHON_FLOW_TEMPLATE);
          showPythonFlowEditor();
          $("build-msg").textContent = "";
          $("build-msg-python").textContent = "Draft — enter a name and save.";
        } else {
          draftIsPython = false;
          clearFlowEditor();
          showJsonFlowEditor();
          $("build-msg-python").textContent = "";
          $("build-msg").textContent = "Draft — enter a name and save.";
        }
        syncDraftListLabel();
        renderScenarioList("scenario-list", scenarioListOnSelect);
        syncScenarioListSelection();
        commitSavedBaseline();
      })();
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest("#panel-groups .groups-add-dropdown")) {
        closeGroupsAddDropdowns();
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeGroupsAddDropdowns();
        return;
      }
      if (!(e.ctrlKey || e.metaKey)) return;
      if (isHelpFilterShortcutsTarget(e.target)) return;
      if (e.key === "s" || e.key === "S") {
        e.preventDefault();
        if (isPythonUi()) {
          void savePythonScenario().catch((err) => showError(err.message));
        } else {
          void saveScenario().catch((err) => showError(err.message));
        }
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (isPythonUi()) {
          void (async () => {
            try {
              await savePythonScenario();
              await startRun($("build-name").value.trim());
            } catch (err) {
              showError(err.message);
            }
          })();
        } else {
          void (async () => {
            try {
              await saveScenario();
              await startRun($("build-name").value.trim());
            } catch (err) {
              showError(err.message);
            }
          })();
        }
      }
    });

    $("flow-list-filter")?.addEventListener("input", () =>
      renderScenarioList("scenario-list", scenarioListOnSelect)
    );

    $("btn-log-clear")?.addEventListener("click", () => {
      const el = $("log-output");
      if (el) el.textContent = "";
    });

    $("btn-log-copy")?.addEventListener("click", async () => {
      const el = $("log-output");
      if (!el) return;
      try {
        await navigator.clipboard.writeText(el.textContent || "");
      } catch {
        appendLog("Copy failed (clipboard unavailable). Select log text manually.");
      }
    });

    window.addEventListener("beforeunload", (e) => {
      const dirty =
        selectedScenario &&
        savedFlowBaseline !== null &&
        captureCurrentFlowSnapshot() !== savedFlowBaseline;
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = "";
    });
  } catch (e) {
    $("health").textContent = "Failed to connect: " + e.message;
  }
})();
