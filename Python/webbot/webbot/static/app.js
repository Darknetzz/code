const $ = (id) => document.getElementById(id);

let scenarios = [];
let selectedScenario = null;
let builderSteps = [];
let ws = null;

function getSelectedScenario() {
  return selectedScenario || scenarios[0]?.name || null;
}

function setSelectedScenario(name) {
  selectedScenario = name;
  document.querySelectorAll(".scenario-item").forEach((btn) => {
    const on = btn.dataset.name === name;
    btn.classList.toggle("selected", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
}

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
  const list = $("run-scenario-list");
  list.innerHTML = "";

  if (scenarios.length === 0) {
    selectedScenario = null;
    const empty = document.createElement("li");
    empty.className = "scenario-list-empty";
    empty.textContent = "No scenarios found";
    list.appendChild(empty);
    return;
  }

  const stillValid =
    selectedScenario && scenarios.some((s) => s.name === selectedScenario);
  if (!stillValid) selectedScenario = scenarios[0].name;

  for (const s of scenarios) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "scenario-item";
    btn.dataset.name = s.name;
    btn.setAttribute("role", "option");

    const nameEl = document.createElement("span");
    nameEl.className = "scenario-item-name";
    nameEl.textContent = s.name;

    const typeEl = document.createElement("span");
    typeEl.className = "scenario-item-type";
    typeEl.textContent = s.type;

    btn.appendChild(nameEl);
    btn.appendChild(typeEl);

    if (s.description) {
      const descEl = document.createElement("span");
      descEl.className = "scenario-item-desc";
      descEl.textContent = s.description;
      btn.appendChild(descEl);
    }

    btn.addEventListener("click", () => setSelectedScenario(s.name));
    li.appendChild(btn);
    list.appendChild(li);
  }

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

  const del = document.createElement("button");
  del.type = "button";
  del.textContent = "x";
  del.title = "Remove field";
  del.onclick = (e) => {
    e.stopPropagation();
    builderSteps[stepIndex].fields.splice(fieldIndex, 1);
    renderSteps();
  };
  wrap.appendChild(del);
  return wrap;
}

function renderStepRow(step, index) {
  const row = document.createElement("div");
  row.className = "step-row";
  row.dataset.stepIndex = String(index);

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
  await api("/api/scenarios", { method: "POST", body: JSON.stringify(doc) });
  $("build-msg").textContent = `Saved "${doc.name}"`;
  await loadScenarios();
  setSelectedScenario(doc.name);
}

async function loadScenarioForEdit() {
  const name = getSelectedScenario();
  const info = scenarios.find((s) => s.name === name);
  if (!info || info.type !== "json") {
    $("build-msg").textContent = "Select a JSON scenario in the Run tab first";
    return;
  }
  const doc = await api(`/api/scenarios/${encodeURIComponent(name)}`);
  $("build-name").value = doc.name;
  $("build-desc").value = doc.description || "";
  $("build-url").value = doc.start_url || "";
  renderScenarioOptions(doc);
  builderSteps = (doc.steps || []).map((s) => normalizeStep({ ...s }));
  renderSteps();
  $("build-msg").textContent = `Loaded "${name}"`;
  document.querySelector('.tab[data-tab="builder"]').click();
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
    renderScenarioOptions();
    $("build-random-between-steps").addEventListener("change", () => renderScenarioOptions(readScenarioOptions()));
    renderSteps();
  } catch (e) {
    $("health").textContent = "Failed to connect: " + e.message;
  }
})();
