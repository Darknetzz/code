const $ = (id) => document.getElementById(id);

let scenarios = [];
let builderSteps = [];
let ws = null;

function appendLog(line) {
  const el = $("log-output");
  el.textContent += line + "\n";
  el.scrollTop = el.scrollHeight;
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
      setRunStatus(msg);
      if (msg.error) appendLog("Error: " + msg.error);
      updateRunButtons(msg.state);
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

function appendLocatorFields(container, step, includeValue) {
  const by = document.createElement("select");
  ["role", "text", "css", "test_id", "label"].forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    if (step.by === v) o.selected = true;
    by.appendChild(o);
  });
  by.dataset.field = "by";
  container.appendChild(by);
  container.appendChild(fieldInput("role", step.role || ""));
  container.appendChild(fieldInput("name", step.name || ""));
  container.appendChild(fieldInput("label", step.label || ""));
  container.appendChild(fieldInput("text", step.text || ""));
  container.appendChild(fieldInput("selector", step.selector || ""));
  container.appendChild(fieldInput("test_id", step.test_id || ""));
  if (includeValue) {
    container.appendChild(fieldInput("value", step.value || ""));
  }
}

function renderFormFieldRow(stepIndex, fieldIndex, field) {
  const wrap = document.createElement("div");
  wrap.className = "form-field-row";
  const by = document.createElement("select");
  ["role", "text", "css", "test_id", "label"].forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    if (field.by === v) o.selected = true;
    by.appendChild(o);
  });
  by.onchange = () => {
    field.by = by.value;
  };
  const selector = fieldInput("selector", field.selector || "");
  selector.oninput = () => {
    field.selector = selector.value;
  };
  const label = fieldInput("label", field.label || "");
  label.oninput = () => {
    field.label = label.value;
  };
  const value = fieldInput("value", field.value || "");
  value.oninput = () => {
    field.value = value.value;
  };
  const del = document.createElement("button");
  del.type = "button";
  del.textContent = "x";
  del.onclick = (e) => {
    e.stopPropagation();
    builderSteps[stepIndex].fields.splice(fieldIndex, 1);
    renderSteps();
  };
  wrap.appendChild(by);
  wrap.appendChild(selector);
  wrap.appendChild(label);
  wrap.appendChild(value);
  wrap.appendChild(del);
  return wrap;
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
  } else if (step.action === "fill") {
    appendLocatorFields(fields, step, true);
  } else if (step.action === "submit_form") {
    const method = document.createElement("select");
    method.dataset.field = "method";
    ["get", "post"].forEach((v) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = v.toUpperCase();
      if ((step.method || "post") === v) o.selected = true;
      method.appendChild(o);
    });
    fields.appendChild(method);
    fields.appendChild(fieldInput("form_selector", step.form_selector || ""));
    fields.appendChild(fieldInput("submit_name", step.submit_name || ""));
    fields.appendChild(fieldInput("submit_selector", step.submit_selector || ""));

    const fieldsLabel = document.createElement("span");
    fieldsLabel.className = "form-fields-label";
    fieldsLabel.textContent = "Fields:";
    fields.appendChild(fieldsLabel);

    const fieldsWrap = document.createElement("div");
    fieldsWrap.className = "form-fields-wrap";
    (step.fields || []).forEach((f, fi) => {
      fieldsWrap.appendChild(renderFormFieldRow(index, fi, f));
    });
    fields.appendChild(fieldsWrap);

    const addField = document.createElement("button");
    addField.type = "button";
    addField.className = "btn-add-field";
    addField.textContent = "+ field";
    addField.onclick = (e) => {
      e.stopPropagation();
      if (!builderSteps[index].fields) builderSteps[index].fields = [];
      builderSteps[index].fields.push({ by: "css", selector: "", value: "" });
      renderSteps();
    };
    fields.appendChild(addField);
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
  const prev = builderSteps[index];
  const action =
    row.querySelector('[data-field="action"]')?.value || prev.action;
  const step = { action };
  row.querySelectorAll("[data-field]").forEach((el) => {
    const key = el.dataset.field;
    if (key === "action") return;
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
    setRunStatus(st);
    updateRunButtons(st.state);
    connectWebSocket();
    builderSteps = [defaultStep("goto")];
    renderSteps();
  } catch (e) {
    $("health").textContent = "Failed to connect: " + e.message;
  }
})();
