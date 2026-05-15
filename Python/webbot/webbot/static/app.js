const $ = (id) => document.getElementById(id);

let scenarios = [];
let selectedScenario = null;
let builderSteps = [];
let ws = null;
let runStepProgress = null;
let runShowStepProgress = false;
let cachedPreviewDoc = null;
let cachedScenarioPreview = null;
let runStatusPollTimer = null;

function getSelectedScenario() {
  return selectedScenario || scenarios[0]?.name || null;
}

function getScenarioInfo(name) {
  return scenarios.find((s) => s.name === name) || null;
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
    default:
      return step.action;
  }
}

function buildStepPlanFromDoc(doc) {
  const items = [];
  const steps = doc.steps || [];
  const hasGoto = steps.some((s) => s.action === "goto");
  let offset = 0;
  if (doc.start_url && !hasGoto) {
    items.push({ index: 1, label: `goto ${doc.start_url}`, status: "pending", error: null });
    offset = 1;
  }
  steps.forEach((s, i) => {
    items.push({
      index: i + 1 + offset,
      label: stepPreviewLabel(s),
      status: "pending",
      error: null,
    });
  });
  return items;
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

function renderRunFlowPreviewBody(loopInfo) {
  const body = $("run-flow-preview-body");
  if (!body) return;
  if (runShowStepProgress && runStepProgress?.length) {
    body.innerHTML = renderRunStepProgressHtml(runStepProgress, loopInfo);
    return;
  }
  const name = getSelectedScenario();
  const info = name ? getScenarioInfo(name) : null;
  if (!name || !info) {
    body.innerHTML = "";
    return;
  }
  if (info.type === "python") {
    body.innerHTML = `<p>${escapeHtml(info.description || "Python scenario")}</p><p class="muted">Defined in source code — open the <strong>Flows</strong> tab to view details. Edit in <code>webbot/scenarios/</code>.</p>`;
    return;
  }
  if (cachedScenarioPreview) {
    body.innerHTML = renderScenarioPreviewHtml(cachedScenarioPreview);
  } else if (cachedPreviewDoc) {
    body.innerHTML = renderFlowPreviewHtml(cachedPreviewDoc);
  }
}

async function initRunStepProgress(scenario) {
  runStepProgress = [];
  try {
    const preview = await fetchScenarioPreview(scenario);
    cachedScenarioPreview = preview;
    runStepProgress = stepPlanFromPreview(preview);
    if (preview.type === "json") {
      try {
        cachedPreviewDoc = await api(`/api/scenarios/${encodeURIComponent(scenario)}`);
      } catch {
        cachedPreviewDoc = null;
      }
    }
  } catch {
    runStepProgress = [];
  }
  runShowStepProgress = true;
  const panel = $("run-flow-preview");
  panel?.classList.remove("hidden");
  renderRunFlowPreviewBody();
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
  renderRunFlowPreviewBody();
}

function applyRunStepProgress(msg) {
  const loopInfo = { loop: msg.loop, loops: msg.loops };

  if (msg.step_progress?.length) {
    runStepProgress = msg.step_progress.map((s) => ({ ...s }));
    runShowStepProgress = true;
    renderRunFlowPreviewBody(loopInfo);
    return;
  }

  if (msg.state === "running" && msg.step && msg.step_label) {
    const idx = msg.step;
    upsertRunStepEntry(idx, msg.step_label, "running");
    runStepProgress.forEach((s) => {
      if (s.index < idx && s.status === "running") s.status = "ok";
    });
    renderRunFlowPreviewBody(loopInfo);
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
    renderRunFlowPreviewBody(loopInfo);
  }
}

function clearRunStepProgress() {
  runStepProgress = null;
  runShowStepProgress = false;
  stopRunStatusPolling();
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

function renderFlowPreviewHtml(doc) {
  return renderScenarioPreviewHtml({
    description: doc.description,
    start_url: doc.start_url,
    random_delay_between_steps: doc.random_delay_between_steps,
    between_steps_min: doc.between_steps_min,
    between_steps_max: doc.between_steps_max,
    between_steps_distribution: doc.between_steps_distribution,
    steps: buildStepPlanFromDoc(doc).map((s) => ({ index: s.index, label: s.label })),
  });
}

function renderPythonFlowView(preview) {
  updatePythonBanner({ name: preview.name, description: preview.description });
  $("flow-python-banner")?.classList.remove("hidden");
  $("flow-python-view")?.classList.remove("hidden");
  $("flow-editor-wrap")?.classList.add("hidden");
  const list = $("flow-python-steps");
  if (list) {
    const steps = preview.steps || [];
    list.innerHTML = steps.length
      ? steps.map((s) => `<li>${escapeHtml(s.label)}</li>`).join("")
      : '<li class="muted">No steps listed — add STEP_LABELS in the scenario module.</li>';
  }
  const src = $("flow-python-source");
  if (src) {
    if (preview.source) {
      src.innerHTML = `<strong>Source:</strong> <code>${escapeHtml(preview.source)}</code>`;
      src.classList.remove("hidden");
    } else {
      src.textContent = "";
      src.classList.add("hidden");
    }
  }
}

function showJsonFlowEditor() {
  $("flow-python-banner")?.classList.add("hidden");
  $("flow-python-view")?.classList.add("hidden");
  $("flow-editor-wrap")?.classList.remove("hidden");
  setFlowEditorMode(true);
}

async function updateRunFlowPreview(name) {
  const panel = $("run-flow-preview");
  const body = $("run-flow-preview-body");
  const editBtn = $("btn-edit-flow");
  if (!panel || !body) return;

  if (!name) {
    panel.classList.add("hidden");
    return;
  }

  const info = getScenarioInfo(name);
  if (!info) {
    panel.classList.add("hidden");
    return;
  }

  panel.classList.remove("hidden");
  if (editBtn) {
    const isJson = info.type === "json";
    editBtn.classList.remove("hidden");
    editBtn.disabled = false;
    editBtn.title = isJson ? "Edit this flow" : "View in Flows tab (read-only)";
    const label = editBtn.querySelector(".btn-label");
    if (label) label.textContent = isJson ? "Edit flow" : "View flow";
    editBtn.setAttribute("aria-label", editBtn.title);
  }

  if (runShowStepProgress && runStepProgress?.length) {
    renderRunFlowPreviewBody();
    return;
  }

  try {
    body.innerHTML = '<p class="muted">Loading…</p>';
    const preview = await fetchScenarioPreview(name);
    cachedScenarioPreview = preview;
    if (info.type === "json") {
      try {
        cachedPreviewDoc = await api(`/api/scenarios/${encodeURIComponent(name)}`);
      } catch {
        cachedPreviewDoc = null;
      }
    } else {
      cachedPreviewDoc = null;
    }
    body.innerHTML = renderScenarioPreviewHtml(preview);
  } catch (e) {
    cachedPreviewDoc = null;
    cachedScenarioPreview = null;
    body.innerHTML = `<p class="status failed">${escapeHtml(e.message)}</p>`;
  }
}

function updateDeleteFlowButton() {
  const btn = $("btn-delete-flow");
  if (!btn) return;
  const info = selectedScenario ? getScenarioInfo(selectedScenario) : null;
  btn.disabled = !info || info.type !== "json";
}

function updatePythonBanner(info) {
  const titleEl = $("flow-python-title");
  const descEl = $("flow-python-desc");
  if (titleEl) titleEl.textContent = info?.name || "Python flow";
  if (descEl) {
    const desc = info?.description?.trim();
    descEl.textContent = desc || "";
    descEl.classList.toggle("hidden", !desc);
  }
}

function setFlowEditorMode(jsonEditable) {
  const wrap = $("flow-editor-wrap");
  const banner = $("flow-python-banner");
  if (banner) banner.classList.toggle("hidden", jsonEditable !== false);
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
  selectedScenario = null;
  syncScenarioListSelection();
  clearFlowEditor();
  showJsonFlowEditor();
  $("build-msg").textContent = "New flow — enter a name and save.";
  updateDeleteFlowButton();
  updateRunFlowPreview(null);
}

async function loadFlowIntoEditor(name) {
  $("build-msg").textContent = "";
  if (!name) {
    newFlow();
    return;
  }

  const info = getScenarioInfo(name);
  if (!info) {
    $("build-msg").textContent = "Flow not found";
    return;
  }

  setSelectedScenario(name, { skipPreview: true });

  if (info.type === "python") {
    try {
      const preview = await fetchScenarioPreview(name);
      cachedScenarioPreview = preview;
      renderPythonFlowView(preview);
      $("build-msg").textContent = "Python flow — view only. Edit source to change steps.";
    } catch (e) {
      $("build-msg").textContent = e.message;
    }
    updateDeleteFlowButton();
    await updateRunFlowPreview(name);
    return;
  }

  showJsonFlowEditor();
  try {
    const doc = await api(`/api/scenarios/${encodeURIComponent(name)}`);
    populateFlowEditor(doc);
    $("build-msg").textContent = `Editing "${name}"`;
    updateDeleteFlowButton();
    await updateRunFlowPreview(name);
  } catch (e) {
    $("build-msg").textContent = e.message;
  }
}

function openFlowsTab(name) {
  document.querySelector('.tab[data-tab="flows"]')?.click();
  if (name) loadFlowIntoEditor(name);
}

async function deleteSelectedFlow() {
  const name = selectedScenario;
  const info = name ? getScenarioInfo(name) : null;
  if (!info || info.type !== "json") return;
  if (!confirm(`Delete flow "${name}"? This cannot be undone.`)) return;
  await api(`/api/scenarios/${encodeURIComponent(name)}`, { method: "DELETE" });
  await loadScenarios();
  newFlow();
  $("build-msg").textContent = `Deleted "${name}"`;
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
  if (!options.skipPreview) {
    if (prev !== selectedScenario) clearRunStepProgress();
    updateRunFlowPreview(name);
  }
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
    nameText.textContent = s.name;
    nameEl.appendChild(nameText);

  const typeEl = document.createElement("span");
  typeEl.className = `scenario-item-type type-${s.type}`;
  if (typeof icon === "function") {
    typeEl.appendChild(icon(s.type === "python" ? "python" : "json", "icon icon-badge"));
  }
  const typeLabel = document.createElement("span");
  typeLabel.textContent = s.type;
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

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "scenario-item-edit btn-icon-only";
  editBtn.title = s.type === "json" ? "Edit flow" : "View flow (read-only)";
  if (typeof enhanceButton === "function") {
    enhanceButton(editBtn, s.type === "json" ? "edit" : "flows", { iconOnly: true, label: editBtn.title });
  } else {
    editBtn.textContent = "✎";
  }
  editBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    openFlowsTab(s.name);
  });
  li.appendChild(editBtn);

  return li;
}

function renderScenarioList(containerId, onSelect) {
  const list = $(containerId);
  if (!list) return;
  list.innerHTML = "";

  if (scenarios.length === 0) {
    const empty = document.createElement("li");
    empty.className = "scenario-list-empty";
    empty.textContent = "No flows found";
    list.appendChild(empty);
    return;
  }

  for (const s of scenarios) {
    list.appendChild(buildScenarioListItem(s, onSelect));
  }
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

  if (scenarios.length === 0) {
    selectedScenario = null;
    renderScenarioList("run-scenario-list", (name) => setSelectedScenario(name));
    renderScenarioList("flows-scenario-list", (name) => loadFlowIntoEditor(name));
    updateRunFlowPreview(null);
    updateDeleteFlowButton();
    return;
  }

  const stillValid =
    selectedScenario && scenarios.some((s) => s.name === selectedScenario);
  if (!stillValid) selectedScenario = scenarios[0].name;

  renderScenarioList("run-scenario-list", (name) => setSelectedScenario(name));
  renderScenarioList("flows-scenario-list", (name) => loadFlowIntoEditor(name));
  setSelectedScenario(selectedScenario);
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

const STEP_TYPES = ["goto", "click", "fill", "submit_form", "delay", "scroll"];

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
    if (helpId && typeof createHelpButton === "function") {
      labRow.appendChild(createHelpButton(helpId));
    }
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
  if (typeof createHelpButton === "function") {
    typeLabRow.appendChild(createHelpButton("step.types"));
  }
  typeWrap.appendChild(typeLabRow);
  typeWrap.appendChild(typeSelect);
  row.appendChild(typeWrap);

  const fields = document.createElement("div");
  fields.className = "step-fields";

  if (step.action === "goto") {
    fields.appendChild(labeledField("url", "URL", step.url || "", "url", "", "step.goto.url"));
  } else if (step.action === "delay") {
    fields.appendChild(fieldSection("Wait time"));
    fields.appendChild(
      labeledField("min", "Min (seconds)", step.min ?? 0.5, "number", "Shortest random wait", "step.delay.min")
    );
    fields.appendChild(
      labeledField("max", "Max (seconds)", step.max ?? 1.2, "number", "Longest random wait", "step.delay.max")
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
    fields.appendChild(fieldSection("Optional long pause"));
    fields.appendChild(
      labeledField(
        "long_pause_chance",
        "Chance (0–1)",
        step.long_pause_chance ?? 0,
        "number",
        "Probability of an extra distraction pause",
        "step.delay.long_pause"
      )
    );
    fields.appendChild(
      labeledField(
        "long_pause_min",
        "Long pause min (s)",
        step.long_pause_min ?? 2,
        "number",
        "",
        "step.delay.long_pause"
      )
    );
    fields.appendChild(
      labeledField(
        "long_pause_max",
        "Long pause max (s)",
        step.long_pause_max ?? 5,
        "number",
        "",
        "step.delay.long_pause"
      )
    );
  } else if (step.action === "scroll") {
    fields.appendChild(fieldSection("Scroll distance"));
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
    fields.appendChild(fieldSection("Wheel ticks"));
    fields.appendChild(
      labeledField(
        "steps_min",
        "Min ticks",
        step.steps_min ?? 3,
        "number",
        "Fewest mouse-wheel steps",
        "step.scroll.ticks"
      )
    );
    fields.appendChild(
      labeledField(
        "steps_max",
        "Max ticks",
        step.steps_max ?? 8,
        "number",
        "Most mouse-wheel steps",
        "step.scroll.ticks"
      )
    );
    fields.appendChild(
      labeledField(
        "step_delay_min",
        "Delay min (s)",
        step.step_delay_min ?? 0.06,
        "number",
        "Pause between ticks (shortest)",
        "step.scroll.ticks"
      )
    );
    fields.appendChild(
      labeledField(
        "step_delay_max",
        "Delay max (s)",
        step.step_delay_max ?? 0.32,
        "number",
        "Pause between ticks (longest)",
        "step.scroll.ticks"
      )
    );
    fields.appendChild(fieldSection("Overscroll"));
    fields.appendChild(
      fieldCheckbox(
        "overscroll",
        "Overscroll then correct",
        step.overscroll !== false,
        "Scroll slightly past target, then scroll back",
        "step.scroll.overscroll"
      )
    );
    fields.appendChild(
      labeledField(
        "overscroll_ratio_min",
        "Overshoot min (ratio)",
        step.overscroll_ratio_min ?? 0.06,
        "number",
        "Fraction of total scroll (e.g. 0.1 = 10%)",
        "step.scroll.overscroll"
      )
    );
    fields.appendChild(
      labeledField(
        "overscroll_ratio_max",
        "Overshoot max (ratio)",
        step.overscroll_ratio_max ?? 0.16,
        "number",
        "",
        "step.scroll.overscroll"
      )
    );
    fields.appendChild(fieldSection("After scroll"));
    fields.appendChild(
      labeledField(
        "pause_after_min",
        "Pause min (s)",
        step.pause_after_min ?? 0.2,
        "number",
        "",
        "step.scroll.after"
      )
    );
    fields.appendChild(
      labeledField(
        "pause_after_max",
        "Pause max (s)",
        step.pause_after_max ?? 0.85,
        "number",
        "",
        "step.scroll.after"
      )
    );
    fields.appendChild(
      fieldCheckbox(
        "variable_step_size",
        "Variable tick size",
        step.variable_step_size !== false,
        "Each wheel tick moves a random amount",
        "step.scroll.after"
      )
    );
  } else if (step.action === "click") {
    if (!step.by) step.by = "role";
    appendLocatorFields(fields, step, false, index);
  } else if (step.action === "fill") {
    if (!step.by) step.by = "css";
    appendLocatorFields(fields, step, true, index);
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
        "form_selector",
        "Form CSS selector",
        step.form_selector || "",
        "text",
        "",
        "step.submit_form.form_selector"
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
      labeledField(
        "submit_selector",
        "Submit CSS selector",
        step.submit_selector || "",
        "text",
        "",
        "step.submit_form.submit"
      )
    );

    const fieldsLabelRow = document.createElement("div");
    fieldsLabelRow.className = "form-fields-label label-row";
    const fieldsLabel = document.createElement("span");
    fieldsLabel.className = "form-fields-label";
    fieldsLabel.textContent = "Fields:";
    fieldsLabelRow.appendChild(fieldsLabel);
    if (typeof createHelpButton === "function") {
      fieldsLabelRow.appendChild(createHelpButton("step.submit_form.fields"));
    }
    fields.appendChild(fieldsLabelRow);

    const fieldsWrap = document.createElement("div");
    fieldsWrap.className = "form-fields-wrap";
    (step.fields || []).forEach((f, fi) => {
      fieldsWrap.appendChild(renderFormFieldRow(index, fi, f));
    });
    fields.appendChild(fieldsWrap);

    const addField = document.createElement("button");
    addField.type = "button";
    addField.className = "btn-add-field";
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
    actions.appendChild(makeIconButton("chevronUp", "Move step up", () => moveStep(index, -1)));
    actions.appendChild(makeIconButton("chevronDown", "Move step down", () => moveStep(index, 1)));
    actions.appendChild(
      makeIconButton("trash", "Remove step", () => removeStep(index), { danger: true })
    );
  } else {
    actions.innerHTML = `
      <button type="button" data-up title="Move step up">↑</button>
      <button type="button" data-down title="Move step down">↓</button>
      <button type="button" class="danger" data-del title="Remove step">×</button>
    `;
    actions.querySelector("[data-up]").onclick = () => moveStep(index, -1);
    actions.querySelector("[data-down]").onclick = () => moveStep(index, 1);
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

function fieldSection(title) {
  const el = document.createElement("div");
  el.className = "field-section-title";
  el.textContent = title;
  return el;
}

function appendFieldLabel(parent, labelText, hint, helpId) {
  const row = document.createElement("div");
  row.className = "label-row";
  const lab = document.createElement("span");
  lab.className = "field-label";
  lab.textContent = labelText;
  if (hint) lab.title = hint;
  row.appendChild(lab);
  if (helpId && typeof createHelpButton === "function") {
    row.appendChild(createHelpButton(helpId));
  }
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
  if (helpId && typeof createHelpButton === "function") {
    label.appendChild(createHelpButton(helpId));
  }
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

function moveStep(index, dir) {
  const j = index + dir;
  if (j < 0 || j >= builderSteps.length) return;
  [builderSteps[index], builderSteps[j]] = [builderSteps[j], builderSteps[index]];
  renderSteps();
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
  container.appendChild(fieldSection("Between-step wait"));
  container.appendChild(
    labeledScenarioField(
      "between_steps_min",
      "Min (seconds)",
      doc.between_steps_min ?? 0.3,
      "number",
      "Shortest pause before the next step"
    )
  );
  container.appendChild(
    labeledScenarioField(
      "between_steps_max",
      "Max (seconds)",
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

async function saveScenario() {
  const doc = collectDocument();
  if (!doc.name) {
    $("build-msg").textContent = "Name is required";
    return;
  }
  if (getScenarioInfo(doc.name)?.type === "python") {
    $("build-msg").textContent = "Cannot save over a built-in Python flow";
    return;
  }
  await api("/api/scenarios", { method: "POST", body: JSON.stringify(doc) });
  $("build-msg").textContent = `Saved "${doc.name}"`;
  await loadScenarios();
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

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`panel-${tab.dataset.tab}`).classList.add("active");
    if (tab.dataset.tab === "flows" && selectedScenario) {
      loadFlowIntoEditor(selectedScenario);
    }
  });
});

$("btn-start").onclick = () => startRun();
$("btn-stop").onclick = () => api("/api/run/stop", { method: "POST" });
$("btn-add-step").onclick = () => {
  const last = builderSteps[builderSteps.length - 1];
  builderSteps.push(defaultStep(last?.action || "goto"));
  renderSteps();
};
$("btn-save").onclick = () => saveScenario().catch((e) => ($("build-msg").textContent = e.message));
$("btn-new-flow")?.addEventListener("click", () => newFlow());
$("btn-delete-flow")?.addEventListener("click", () =>
  deleteSelectedFlow().catch((e) => ($("build-msg").textContent = e.message))
);
$("btn-edit-flow")?.addEventListener("click", () => {
  const name = getSelectedScenario();
  if (name) openFlowsTab(name);
});
$("btn-test-run").onclick = async () => {
  try {
    await saveScenario();
    document.querySelector('.tab[data-tab="run"]').click();
    await startRun($("build-name").value.trim());
  } catch (e) {
    $("build-msg").textContent = e.message;
  }
};

(async () => {
  try {
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
    }
    connectWebSocket();
    if (selectedScenario) {
      await loadFlowIntoEditor(selectedScenario);
      if (runShowStepProgress && runStepProgress?.length) renderRunFlowPreviewBody();
    } else {
      newFlow();
    }
    $("build-random-between-steps").addEventListener("change", () => renderScenarioOptions(readScenarioOptions()));
  } catch (e) {
    $("health").textContent = "Failed to connect: " + e.message;
  }
})();
