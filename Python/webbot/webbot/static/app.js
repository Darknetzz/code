const $ = (id) => document.getElementById(id);

let scenarios = [];
let builderSteps = [];
let ws = null;

function appendLog(line) {
  const el = $("log-output");
  el.textContent += line + "\n";
  el.scrollTop = el.scrollHeight;
}

function setRunStatus(state, detail = "") {
  const el = $("run-status");
  el.className = "status " + (state || "muted");
  const labels = {
    idle: "Idle",
    running: "Running…",
    completed: "Completed",
    failed: "Failed",
    stopped: "Stopped",
  };
  el.textContent = (labels[state] || state) + (detail ? ` — ${detail}` : "");
}

function updateRunButtons(state) {
  const running = state === "running";
  $("btn-start").disabled = running;
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
  const sel = $("run-scenario");
  sel.innerHTML = "";
  for (const s of scenarios) {
    const opt = document.createElement("option");
    opt.value = s.name;
    opt.textContent = `${s.name} (${s.type})`;
    sel.appendChild(opt);
  }
}

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws/logs`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "log") appendLog(msg.message);
    if (msg.type === "status") {
      setRunStatus(msg.state, msg.loop && msg.loops ? `loop ${msg.loop}/${msg.loops}` : "");
      if (msg.error) appendLog("Error: " + msg.error);
      updateRunButtons(msg.state);
    }
  };
  ws.onclose = () => setTimeout(connectWebSocket, 2000);
}

const STEP_TYPES = ["goto", "click", "delay", "scroll"];

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
      return { action: "delay", min: 0.5, max: 1.2 };
    case "scroll":
      return { action: "scroll", delta_y: 300 };
    default:
      return { action };
  }
}

function renderStepRow(step, index) {
  const row = document.createElement("div");
  row.className = "step-row";
  row.dataset.index = index;

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
  row.appendChild(typeSelect);

  const fields = document.createElement("div");
  fields.className = "step-fields";

  if (step.action === "goto") {
    fields.appendChild(fieldInput("url", step.url || ""));
  } else if (step.action === "delay") {
    fields.appendChild(fieldInput("min", step.min ?? 0.5, "number"));
    fields.appendChild(fieldInput("max", step.max ?? 1.2, "number"));
  } else if (step.action === "scroll") {
    fields.appendChild(fieldInput("delta_y", step.delta_y ?? 300, "number"));
  } else if (step.action === "click") {
    const by = document.createElement("select");
    ["role", "text", "css", "test_id"].forEach((v) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = v;
      if (step.by === v) o.selected = true;
      by.appendChild(o);
    });
    by.dataset.field = "by";
    fields.appendChild(by);
    fields.appendChild(fieldInput("role", step.role || ""));
    fields.appendChild(fieldInput("name", step.name || ""));
    fields.appendChild(fieldInput("text", step.text || ""));
    fields.appendChild(fieldInput("selector", step.selector || ""));
    fields.appendChild(fieldInput("test_id", step.test_id || ""));
  }

  row.appendChild(fields);

  const actions = document.createElement("div");
  actions.className = "step-actions";
  actions.innerHTML = `
    <button type="button" data-up>↑</button>
    <button type="button" data-down>↓</button>
    <button type="button" data-del>×</button>
  `;
  actions.querySelector("[data-up]").onclick = () => moveStep(index, -1);
  actions.querySelector("[data-down]").onclick = () => moveStep(index, 1);
  actions.querySelector("[data-del]").onclick = () => removeStep(index);
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
  inp.placeholder = name;
  inp.dataset.field = name;
  inp.value = value;
  return inp;
}

function syncStepFromDom(index, row) {
  const action =
    row.querySelector('[data-field="action"]')?.value || builderSteps[index].action;
  const step = { action };
  row.querySelectorAll("[data-field]").forEach((el) => {
    const key = el.dataset.field;
    if (key === "action") return;
    let val = el.value;
    if (el.type === "number") val = parseFloat(val);
    if (val !== "" && val !== null && !Number.isNaN(val)) step[key] = val;
  });
  builderSteps[index] = step;
}

function renderSteps() {
  const list = $("steps-list");
  list.innerHTML = "";
  builderSteps.forEach((step, i) => list.appendChild(renderStepRow(step, i)));
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

function collectDocument() {
  return {
    name: $("build-name").value.trim(),
    description: $("build-desc").value.trim(),
    start_url: $("build-url").value.trim(),
    steps: builderSteps.map((s) => ({ ...s })),
  };
}

async function saveScenario() {
  const doc = collectDocument();
  if (!doc.name) {
    $("build-msg").textContent = "Name is required";
    return;
  }
  await api("/api/scenarios", { method: "POST", body: JSON.stringify(doc) });
  $("build-msg").textContent = `Saved "${doc.name}"`;
  await loadScenarios();
  $("run-scenario").value = doc.name;
}

async function loadScenarioForEdit() {
  const name = $("run-scenario").value;
  const info = scenarios.find((s) => s.name === name);
  if (!info || info.type !== "json") {
    $("build-msg").textContent = "Select a JSON scenario in the Run tab first";
    return;
  }
  const doc = await api(`/api/scenarios/${encodeURIComponent(name)}`);
  $("build-name").value = doc.name;
  $("build-desc").value = doc.description || "";
  $("build-url").value = doc.start_url || "";
  builderSteps = doc.steps || [];
  renderSteps();
  $("build-msg").textContent = `Loaded "${name}"`;
  document.querySelector('.tab[data-tab="builder"]').click();
}

async function startRun(scenarioName) {
  const body = {
    scenario: scenarioName || $("run-scenario").value,
    loops: parseInt($("run-loops").value, 10) || 1,
    pause_between_loops_sec: parseFloat($("run-pause").value) || 0,
    headless: $("run-headless").checked,
    channel: "chrome",
    slow_mo: 0,
  };
  $("log-output").textContent = "";
  await api("/api/run", { method: "POST", body: JSON.stringify(body) });
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`panel-${tab.dataset.tab}`).classList.add("active");
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
$("btn-load").onclick = () => loadScenarioForEdit().catch((e) => ($("build-msg").textContent = e.message));
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
    setRunStatus(st.state);
    updateRunButtons(st.state);
    connectWebSocket();
    builderSteps = [defaultStep("goto")];
    renderSteps();
  } catch (e) {
    $("health").textContent = "Failed to connect: " + e.message;
  }
})();
