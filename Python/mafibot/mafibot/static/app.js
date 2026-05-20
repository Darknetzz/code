const $ = (id) => document.getElementById(id);

/** All gameplay actions the brain can schedule (hotel handled separately). */
const ACTION_CATALOG = [
  {
    id: "hospital",
    label: "Hospital (Sykehus)",
    description:
      "Opens the Sykehus tab and heals when Helse is below your threshold. Runs before other actions while injured. Can run in the hotel.",
  },
  {
    id: "crime",
    label: "Crime (Kriminalitet)",
    description:
      "Opens Kriminalitet when ready. Enable Enkel, Tung, and/or Stjel (or All). Pick specific crimes per section; bot rotates when multiple are enabled. Leaves hotel first.",
  },
  {
    id: "work",
    label: "Work (Arbeid)",
    description:
      "Opens the Arbeid tab and clicks work when the job timer is ready. Separate from sidebar business income. Can run in the hotel.",
  },
  {
    id: "business",
    label: "Business (Mine bedrifter)",
    description:
      "Opens Mine bedrifter in the sidebar and clicks income/work buttons (hent, inntekt) when business income is ready. Can run while still in the hotel.",
  },
  {
    id: "ship",
    label: "Ship (Mitt rederi)",
    description:
      "Opens Mitt rederi and sends the ship when ready. Configure routes per current port (destinations vary by location) or fallback harbors. Can run in the hotel.",
  },
  {
    id: "travel",
    label: "Travel (Flyplass)",
    description:
      "Opens Flyplass and starts travel when available. Must leave the hotel first, then re-books afterward.",
  },
  {
    id: "drugs",
    label: "Drugs",
    description:
      "Buy in Kabul, sell in New York/Oslo/Detroit/Rio/Las Vegas (configurable). Requires Travel enabled before Drugs in the list. Bot flies to the right city first.",
  },
  {
    id: "bank",
    label: "Bank",
    description:
      "Opens bank. With auto-balance: deposits or withdraws to keep wallet (Penger) near your target ± tolerance. Without auto: clicks generic innskudd/uttak. Must leave the hotel first.",
  },
  {
    id: "messages",
    label: "Messages",
    description:
      "Opens Meldinger, may open inbox threads, and tries to reply. Runs when you have unread messages or after social_interval_minutes (default 45). Max 8 replies per hour. Stays in hotel.",
  },
  {
    id: "family",
    label: "Family",
    description:
      "Opens Familie on a timer (social_interval_minutes). Accepts invites (Godta/Aksepter) if shown; otherwise just visits the page. Stays in hotel.",
  },
  {
    id: "minions",
    label: "Minions (Undersåtter)",
    description:
      "Opens Undersåtter when enabled and cooldown is clear. Good for rank progression. Can run in the hotel.",
  },
  {
    id: "missions",
    label: "Missions (Oppdrag)",
    description:
      "Starts a mission when Oppdrag shows Klar. Skips if already on a mission. Can run in the hotel.",
  },
  {
    id: "organized_crime",
    label: "Organized crime",
    description:
      "Opens Organisert Kriminalitet and clicks Utfør when ready. Must leave the hotel first.",
  },
  {
    id: "market",
    label: "Market (Marked)",
    description:
      "Opens Marked for buy/sell when enabled. Rate-limited per hour. Must leave the hotel first.",
  },
  {
    id: "murder",
    label: "Murder (combat)",
    description:
      "Opens murder/skyt, fills a target username from your list, then shoots if aggression allows. Will not run without targets or with blank names. Must leave the hotel. High ban risk.",
  },
];

/** Actions with extra config panels (shown only when enabled in the list). */
const ACTION_OPTION_PANELS = {
  hospital: "action-options-hospital",
  crime: "action-options-crime",
  work: "action-options-work",
  business: "action-options-business",
  minions: "action-options-minions",
  missions: "action-options-missions",
  organized_crime: "action-options-organized-crime",
  market: "action-options-market",
  ship: "action-options-ship",
  travel: "action-options-travel",
  drugs: "action-options-drugs",
  bank: "action-options-bank",
  messages: "action-options-messages",
  family: "action-options-family",
  murder: "action-options-murder",
};

/** World-map cities — values must match Flyplass / in-game labels. */
const GAME_CITIES = [
  { value: "Las Vegas", label: "Las Vegas" },
  { value: "Detroit", label: "Detroit" },
  { value: "New York", label: "New York" },
  { value: "Rio", label: "Rio de Janeiro" },
  { value: "London", label: "London" },
  { value: "Oslo", label: "Oslo" },
  { value: "Mogadishu", label: "Mogadishu" },
  { value: "Kabul", label: "Kabul" },
  { value: "Kuala Lumpur", label: "Kuala Lumpur" },
];

const travelCityInputs = new Map();
let travelCityListBuilt = false;

function ensureTravelCityList() {
  const container = $("cfg-travel-destinations-list");
  if (!container || travelCityListBuilt) return;
  travelCityListBuilt = true;
  for (const city of GAME_CITIES) {
    const slug = city.value.replace(/\s+/g, "-").toLowerCase();
    const id = `cfg-travel-city-${slug}`;
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = city.value;
    input.id = id;
    travelCityInputs.set(city.value, input);
    label.htmlFor = id;
    label.appendChild(input);
    label.append(document.createTextNode(city.label));
    container.appendChild(label);
  }
}

function loadTravelDestinationsFromDoc(selected) {
  ensureTravelCityList();
  const want = new Set((selected || []).map((s) => String(s).trim()).filter(Boolean));
  for (const [value, input] of travelCityInputs) {
    input.checked = want.has(value);
  }
}

function getTravelDestinationsFromUi() {
  ensureTravelCityList();
  return GAME_CITIES.filter((c) => travelCityInputs.get(c.value)?.checked).map(
    (c) => c.value
  );
}

function formatShipRoutes(routes) {
  if (!routes || typeof routes !== "object") return "";
  return Object.keys(routes)
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }))
    .map((origin) => {
      const dests = routes[origin];
      return `${origin}: ${(Array.isArray(dests) ? dests : []).join(", ")}`;
    })
    .join("\n");
}

function parseShipRoutes(text) {
  const routes = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const sep = trimmed.includes(":") ? ":" : trimmed.includes("->") ? "->" : null;
    if (!sep) continue;
    const idx = trimmed.indexOf(sep);
    const origin = trimmed.slice(0, idx).trim();
    const destPart = trimmed.slice(idx + sep.length).trim();
    const dests = destPart
      .split(/[,|]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (origin && dests.length) routes[origin] = dests;
  }
  return routes;
}

function effectiveInterval(doc, field, fallbackField = "social_interval_minutes") {
  const v = doc[field];
  if (v && v > 0) return v;
  const fb = doc[fallbackField];
  return fb && fb > 0 ? fb : 45;
}

const CRIME_SECTIONS = [
  { id: "enkel", label: "Enkel kriminalitet (Utfør)" },
  { id: "tung", label: "Tung kriminalitet (Utfør)" },
  { id: "stjel", label: "Stjel" },
];

const CRIME_OPTIONS = {
  enkel: [
    { id: "automat", label: "Bryt opp en spilleautomat" },
    { id: "kiosk", label: "Ran en kiosk" },
    { id: "gate", label: "Ran tilfeldig person på gata" },
    { id: "butikk", label: "Nask fra en butikk" },
  ],
  tung: [
    { id: "pengetransport", label: "Ran en pengetransport" },
    { id: "bensin", label: "Ran en bensinstasjon" },
  ],
  stjel: [
    { id: "garasje", label: "Stjel fra garasjen" },
    { id: "vapen", label: "Stjel fra våpenlageret" },
    { id: "penger", label: "Stjel penger" },
  ],
};

const crimeSectionInputs = new Map();
const crimeOptionInputs = new Map();
let crimeUiBuilt = false;

function migrateLegacyCrimeDoc(doc) {
  if (doc.crime_actions && doc.crime_actions.length) {
    return doc;
  }
  const actions = [];
  if (doc.crime_kind === "steal") {
    actions.push("stjel");
  } else if (doc.crime_perform_type === "tung") {
    actions.push("tung");
  } else if (doc.crime_perform_type === "lett") {
    actions.push("enkel");
  } else if (doc.crime_kind === "perform") {
    actions.push("enkel", "tung");
  } else {
    actions.push("enkel");
  }
  const next = { ...doc, crime_actions: actions };
  if (doc.crime_steal_what && !next.crime_steal_items?.length) {
    const w = String(doc.crime_steal_what).toLowerCase();
    const match = CRIME_OPTIONS.stjel.find(
      (o) => o.id === w || o.label.toLowerCase().includes(w)
    );
    if (match) next.crime_steal_items = [match.id];
  }
  return next;
}

function crimeChoicesContainerId(sectionId) {
  return sectionId === "stjel" ? "cfg-crime-stjel-choices" : `cfg-crime-${sectionId}-choices`;
}

function updateCrimeStealUsernameVisibility() {
  const wrap = $("cfg-crime-steal-username-wrap");
  if (!wrap) return;
  wrap.classList.toggle("hidden", $("cfg-crime-steal-target").value !== "specific");
}

function updateCrimePanelsVisibility() {
  $("cfg-crime-enkel-choices-wrap")?.classList.toggle(
    "hidden",
    !crimeSectionInputs.get("enkel")?.checked
  );
  $("cfg-crime-tung-choices-wrap")?.classList.toggle(
    "hidden",
    !crimeSectionInputs.get("tung")?.checked
  );
  $("cfg-crime-stjel-wrap")?.classList.toggle("hidden", !crimeSectionInputs.get("stjel")?.checked);
  updateCrimeStealUsernameVisibility();
}

function syncCrimeAllCheckbox() {
  const allEl = $("cfg-crime-all");
  if (!allEl || crimeSectionInputs.size === 0) return;
  allEl.checked = [...crimeSectionInputs.values()].every((i) => i.checked);
}

function ensureCrimeUi() {
  if (crimeUiBuilt) return;
  crimeUiBuilt = true;
  const toggles = $("cfg-crime-section-toggles");
  if (!toggles) return;

  for (const sec of CRIME_SECTIONS) {
    const label = document.createElement("label");
    label.className = "crime-section-toggle";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = sec.id;
    input.id = `cfg-crime-action-${sec.id}`;
    crimeSectionInputs.set(sec.id, input);
    label.appendChild(input);
    label.append(document.createTextNode(sec.label));
    toggles.appendChild(label);
  }

  for (const [sectionId, options] of Object.entries(CRIME_OPTIONS)) {
    const container = $(crimeChoicesContainerId(sectionId));
    if (!container) continue;
    const entries = [];
    for (const opt of options) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = opt.id;
      input.id = `cfg-crime-opt-${sectionId}-${opt.id}`;
      label.appendChild(input);
      label.append(document.createTextNode(opt.label));
      container.appendChild(label);
      entries.push({ id: opt.id, el: input });
    }
    crimeOptionInputs.set(sectionId, entries);
  }

  $("cfg-crime-all")?.addEventListener("change", () => {
    const on = $("cfg-crime-all").checked;
    for (const input of crimeSectionInputs.values()) {
      input.checked = on;
    }
    updateCrimePanelsVisibility();
  });
  for (const input of crimeSectionInputs.values()) {
    input.addEventListener("change", () => {
      syncCrimeAllCheckbox();
      updateCrimePanelsVisibility();
    });
  }
  $("cfg-crime-steal-target")?.addEventListener("change", updateCrimeStealUsernameVisibility);
}

function loadCrimeFromDoc(doc) {
  const migrated = migrateLegacyCrimeDoc(doc);
  ensureCrimeUi();
  const enabled = new Set(migrated.crime_actions || ["enkel"]);
  for (const [id, input] of crimeSectionInputs) {
    input.checked = enabled.has(id);
  }
  syncCrimeAllCheckbox();
  const applyChoices = (sectionId, list) => {
    const want = new Set(list || []);
    for (const { id, el } of crimeOptionInputs.get(sectionId) || []) {
      el.checked = want.size > 0 && want.has(id);
    }
  };
  applyChoices("enkel", migrated.crime_enkel_choices);
  applyChoices("tung", migrated.crime_tung_choices);
  applyChoices("stjel", migrated.crime_steal_items);
  const rot = $("cfg-crime-rotate");
  if (rot) rot.checked = migrated.crime_rotate_actions !== false;
  $("cfg-crime-steal-target").value = migrated.crime_steal_target_mode || "random";
  $("cfg-crime-steal-username").value = migrated.crime_steal_username || "";
  updateCrimePanelsVisibility();
}

function appendCrimeToPayload(payload) {
  const actions = [];
  for (const [id, input] of crimeSectionInputs) {
    if (input.checked) actions.push(id);
  }
  const gather = (sectionId) =>
    (crimeOptionInputs.get(sectionId) || [])
      .filter(({ el }) => el.checked)
      .map(({ id }) => id);
  payload.crime_actions = actions;
  payload.crime_enkel_choices = gather("enkel");
  payload.crime_tung_choices = gather("tung");
  payload.crime_steal_items = gather("stjel");
  payload.crime_rotate_actions = $("cfg-crime-rotate")?.checked !== false;
  payload.crime_steal_target_mode = $("cfg-crime-steal-target").value || "random";
  payload.crime_steal_username = $("cfg-crime-steal-username").value.trim();
  delete payload.crime_kind;
  delete payload.crime_perform_type;
  delete payload.crime_steal_what;
}

function uiAuthHeaders() {
  const token = sessionStorage.getItem("mafibot_ui_token") || "";
  const h = { "Content-Type": "application/json" };
  if (token) h["X-Mafibot-Token"] = token;
  return h;
}

function loadActionOptionsFromDoc(doc) {
  const crimeHp = $("cfg-crime-min-health");
  crimeHp.value =
    doc.crime_min_health_percent != null && doc.crime_min_health_percent !== ""
      ? doc.crime_min_health_percent
      : "";
  loadCrimeFromDoc(doc);
  $("cfg-crime-buttons").value = (doc.crime_button_labels || []).join(", ");
  $("cfg-hospital-threshold").value = doc.hospital_health_threshold ?? 80;
  $("cfg-business-income-only").checked = doc.business_only_when_income_ready !== false;
  $("cfg-ship-in-port").checked = doc.ship_only_when_in_port !== false;
  $("cfg-ship-routes").value = formatShipRoutes(doc.ship_routes || {});
  $("cfg-ship-destinations").value = (doc.ship_destinations || []).join("\n");
  $("cfg-ship-rotate").checked = !!doc.ship_rotate_destinations;
  loadTravelDestinationsFromDoc(doc.travel_destinations);
  $("cfg-drugs-prefer").value = doc.drugs_prefer || "any";
  $("cfg-drugs-buy-city").value = doc.drugs_buy_city || "Kabul";
  $("cfg-drugs-sell-cities").value = (doc.drugs_sell_cities || [
    "New York",
    "Oslo",
    "Detroit",
    "Rio",
    "Las Vegas",
  ]).join("\n");
  $("cfg-bank-auto").checked = !!doc.bank_auto_balance;
  $("cfg-bank-keep").value = doc.bank_keep_cash_on_hand ?? 100000;
  $("cfg-bank-tolerance").value = doc.bank_balance_tolerance ?? 25000;
  $("cfg-messages-interval").value = effectiveInterval(doc, "messages_interval_minutes");
  $("cfg-messages-max-hour").value = doc.messages_max_per_hour ?? 8;
  $("cfg-messages-unread-only").checked = !!doc.messages_only_when_unread;
  $("cfg-family-interval").value = effectiveInterval(doc, "family_interval_minutes");
  $("cfg-family-auto-accept").checked = doc.family_auto_accept !== false;
  $("cfg-murder-targets").value = (doc.murder_targets || []).join("\n");
  $("cfg-murder-rotate").checked = !!doc.murder_rotate_targets;
  if ($("cfg-missions-mode")) $("cfg-missions-mode").value = doc.missions_mode || "start_only";
  if ($("cfg-minions-action")) $("cfg-minions-action").value = doc.minions_action || "train";
  if ($("cfg-org-crime-difficulty")) {
    $("cfg-org-crime-difficulty").value = doc.organized_crime_difficulty || "auto";
  }
  if ($("cfg-murder-mode")) $("cfg-murder-mode").value = doc.murder_mode || "static_targets";
  if ($("cfg-murder-shoot")) $("cfg-murder-shoot").checked = doc.murder_actually_shoot !== false;
  window.MafibotConfigPanel?.updateMurderTargetsVisibility();
}

function appendActionOptionsToPayload(payload) {
  const crimeHpRaw = $("cfg-crime-min-health").value.trim();
  payload.crime_min_health_percent = crimeHpRaw ? parseInt(crimeHpRaw, 10) : null;
  appendCrimeToPayload(payload);
  payload.crime_button_labels = $("cfg-crime-buttons").value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  payload.hospital_health_threshold =
    parseInt($("cfg-hospital-threshold").value, 10) || 80;
  payload.business_only_when_income_ready = $("cfg-business-income-only").checked;
  payload.ship_only_when_in_port = $("cfg-ship-in-port").checked;
  payload.ship_routes = parseShipRoutes($("cfg-ship-routes").value);
  payload.ship_destinations = $("cfg-ship-destinations").value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  payload.ship_rotate_destinations = $("cfg-ship-rotate").checked;
  payload.travel_destinations = getTravelDestinationsFromUi();
  payload.drugs_prefer = $("cfg-drugs-prefer").value || "any";
  payload.drugs_buy_city = $("cfg-drugs-buy-city").value.trim() || "Kabul";
  payload.drugs_sell_cities = $("cfg-drugs-sell-cities").value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  payload.bank_auto_balance = $("cfg-bank-auto").checked;
  payload.bank_keep_cash_on_hand = parseInt($("cfg-bank-keep").value, 10) || 0;
  payload.bank_balance_tolerance = parseInt($("cfg-bank-tolerance").value, 10) || 0;
  payload.messages_interval_minutes = parseInt($("cfg-messages-interval").value, 10) || 45;
  payload.messages_max_per_hour = parseInt($("cfg-messages-max-hour").value, 10) ?? 8;
  payload.messages_only_when_unread = $("cfg-messages-unread-only").checked;
  payload.family_interval_minutes = parseInt($("cfg-family-interval").value, 10) || 45;
  payload.family_auto_accept = $("cfg-family-auto-accept").checked;
  payload.murder_targets = $("cfg-murder-targets").value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  payload.murder_rotate_targets = $("cfg-murder-rotate").checked;
  if ($("cfg-missions-mode")) payload.missions_mode = $("cfg-missions-mode").value;
  if ($("cfg-minions-action")) payload.minions_action = $("cfg-minions-action").value;
  if ($("cfg-org-crime-difficulty")) {
    payload.organized_crime_difficulty = $("cfg-org-crime-difficulty").value;
  }
  if ($("cfg-murder-mode")) payload.murder_mode = $("cfg-murder-mode").value;
  if ($("cfg-murder-shoot")) {
    payload.murder_actually_shoot = $("cfg-murder-shoot").checked;
  }
  return payload;
}

const ECONOMY_ACTION_IDS = new Set([
  "hospital",
  "crime",
  "work",
  "business",
  "minions",
  "missions",
  "organized_crime",
  "ship",
  "travel",
  "drugs",
  "bank",
  "market",
]);

let ws = null;
let elapsedTimer = null;
let lastStatus = null;
let profileCatalog = [];

function api(path, options = {}) {
  return fetch(path, {
    headers: { ...uiAuthHeaders(), ...(options.headers || {}) },
    ...options,
  }).then(async (res) => {
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!res.ok) {
      const detail = data?.detail || data || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  });
}

function formatElapsed(sec) {
  if (sec == null || Number.isNaN(sec)) return "—";
  const s = Math.floor(sec);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function formatCooldownRemaining(sec) {
  if (sec == null || Number.isNaN(sec) || sec <= 0) return "—";
  const s = Math.ceil(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function renderActiveCooldowns(cooldowns) {
  const list = $("st-cooldowns");
  list.replaceChildren();
  const active = (cooldowns || []).filter((cd) => cd && cd.id);
  if (!active.length) {
    const li = document.createElement("li");
    li.className = "cooldown-empty muted";
    li.textContent = "None";
    list.appendChild(li);
    return;
  }
  for (const cd of active) {
    const li = document.createElement("li");
    const label = document.createElement("span");
    label.className = "cooldown-label";
    label.textContent = cd.label || cd.id;
    const eta = document.createElement("span");
    eta.className = "cooldown-eta";
    eta.dataset.readyAt = cd.ready_at || "";
    eta.textContent = formatCooldownRemaining(cd.remaining_sec);
    li.append(label, eta);
    list.appendChild(li);
  }
}

function tickCooldownCountdowns() {
  const now = Date.now();
  $("st-cooldowns").querySelectorAll(".cooldown-eta[data-ready-at]").forEach((el) => {
    const readyAt = el.dataset.readyAt;
    if (!readyAt) return;
    const remaining = (new Date(readyAt).getTime() - now) / 1000;
    el.textContent = formatCooldownRemaining(remaining);
  });
}

function formatLogLine(raw) {
  if (!raw) return "";
  const uiMatch = raw.match(/^\d{4}-\d{2}-\d{2}T[\d:.]+ UI: (.*)$/);
  if (uiMatch) {
    return `[${new Date().toLocaleTimeString()}] ${uiMatch[1]}`;
  }
  const isoMatch = raw.match(
    /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),?\d* \w+ mafibot[^:]*: (.*)$/
  );
  if (isoMatch) {
    const d = new Date(isoMatch[1].replace(" ", "T"));
    const ts = Number.isNaN(d.getTime())
      ? isoMatch[1]
      : d.toLocaleTimeString();
    return `[${ts}] ${isoMatch[2]}`;
  }
  return raw;
}

function appendLog(message, { fromServer = false } = {}) {
  const el = $("log-output");
  const line = document.createElement("p");
  line.className = "log-line";
  line.textContent = formatLogLine(message) || message;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
  if (!fromServer && message?.trim()) {
    api("/api/logs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message.trim() }),
    }).catch(() => {});
  }
}

function renderLogLines(lines) {
  const el = $("log-output");
  el.replaceChildren();
  for (const raw of lines) {
    appendLog(raw, { fromServer: true });
  }
}

async function loadPersistedLogs() {
  try {
    const data = await api("/api/logs?limit=400");
    const openBtn = $("btn-open-log");
    if (openBtn && data.path) {
      openBtn.title = data.path;
    }
    if (data.lines?.length) {
      renderLogLines(data.lines);
    }
  } catch (e) {
    console.warn("load logs", e);
  }
}

function setBadge(state) {
  const s = (state || "idle").toLowerCase();
  for (const id of ["status-badge", "global-status-badge"]) {
    const badge = $(id);
    if (!badge) continue;
    badge.textContent = state || "idle";
    badge.className = `badge ${s}`;
  }
}

function updateRunControls(state) {
  const busy = ["running", "login", "discover"].includes(state);
  const label = state || "idle";
  for (const id of ["global-status-dot"]) {
    const dot = $(id);
    if (!dot) continue;
    dot.classList.toggle("running", busy);
    dot.classList.toggle("stopped", !busy);
  }
  const startBtn = $("btn-start-run");
  const stopBtn = $("btn-stop");
  if (startBtn) startBtn.disabled = busy;
  if (stopBtn) stopBtn.disabled = !busy;
}

function setGlobalStatusField(id, text, { visible = true } = {}) {
  const el = $(id);
  if (!el) return;
  const show = visible && Boolean(String(text || "").trim());
  el.textContent = show ? text : "";
  el.classList.toggle("hidden", !show);
}

function updateGlobalStatusBar(st) {
  const g = st.game || {};
  const elapsed =
    st.elapsed_sec != null && !Number.isNaN(st.elapsed_sec)
      ? formatElapsed(st.elapsed_sec)
      : "";
  setGlobalStatusField(
    "global-st-profile",
    st.profile ? `Profile: ${st.profile}` : ""
  );
  setGlobalStatusField("global-st-elapsed", elapsed ? `Elapsed: ${elapsed}` : "");
  setGlobalStatusField(
    "global-st-action",
    st.last_action ? `Action: ${st.last_action}` : ""
  );
  setGlobalStatusField("global-st-message", st.last_message || "");
  setGlobalStatusField(
    "global-st-money",
    g.money != null ? `${formatKr(g.money)} kr` : ""
  );
  const hasDetail = [
    st.profile,
    elapsed,
    st.last_action,
    st.last_message,
    g.money != null ? g.money : null,
  ].some((v) => v != null && v !== "");
  const hint = $("global-status-idle-hint");
  if (hint) {
    hint.classList.toggle("hidden", hasDetail || st.state !== "idle");
  }
}

function applyStatus(st) {
  lastStatus = st;
  setBadge(st.state);
  updateRunControls(st.state);
  $("st-profile").textContent = st.profile || "—";
  const elapsedText = formatElapsed(st.elapsed_sec);
  $("st-elapsed").textContent = elapsedText;
  const g = st.game || {};
  $("st-hotel").textContent = g.in_hotel ? "yes" : "no";
  $("st-money").textContent = g.money != null ? String(g.money) : "—";
  updateGlobalStatusBar(st);
  $("st-health").textContent = g.health_percent != null ? `${g.health_percent}%` : "—";
  $("st-location").textContent = g.location || "—";
  $("st-crime").textContent = g.crime_ready ? "yes" : "no";
  const hh = $("st-happy-hour");
  if (hh) {
    hh.textContent = g.happy_hour_active
      ? (g.happy_hour_buffs || []).join(", ") || "active"
      : "no";
  }
  const miss = $("st-mission");
  if (miss) {
    const parts = [];
    if (g.mission_number != null) parts.push(`#${g.mission_number}`);
    if (g.mission_progress_current != null && g.mission_progress_total != null) {
      parts.push(`${g.mission_progress_current}/${g.mission_progress_total}`);
    }
    if (g.mission_requirement_hint) parts.push(g.mission_requirement_hint);
    miss.textContent = parts.length ? parts.join(" · ") : "—";
  }
  const combat = $("st-combat");
  if (combat) {
    const a = g.attack != null ? `A${g.attack}` : "";
    const p = g.protection != null ? `P${g.protection}` : "";
    combat.textContent = [a, p].filter(Boolean).join(" / ") || "—";
  }
  const flags = $("st-flags");
  if (flags) {
    const f = [];
    if (g.feriemodus) f.push("ferie");
    if (g.kidnapped) f.push("kidnappet");
    if (g.startbeskyttelse) f.push("startbeskyttelse");
    if (g.family_war_active) f.push("krig");
    flags.textContent = f.length ? f.join(", ") : "—";
  }
  renderActiveCooldowns(g.active_cooldowns);
  $("st-action").textContent = st.last_action || "—";
  $("st-message").textContent = st.last_message || "—";
  const idleEl = $("st-idle");
  if (idleEl) {
    idleEl.textContent = st.idle_detail || "—";
    idleEl.classList.toggle("hidden", !st.idle_detail);
  }
  const parseEl = $("st-parse-error");
  const playbookEl = $("st-parse-playbook");
  if (parseEl) {
    if (st.parse_error?.detail) {
      parseEl.textContent = st.parse_error.detail;
      if (st.parse_error.screenshot_path) {
        parseEl.textContent += ` · screenshot: ${st.parse_error.screenshot_path}`;
      }
      parseEl.classList.remove("hidden");
    } else {
      parseEl.classList.add("hidden");
    }
  }
  if (playbookEl) {
    if (st.parse_playbook) {
      playbookEl.textContent = st.parse_playbook;
      playbookEl.classList.remove("hidden");
    } else {
      playbookEl.classList.add("hidden");
    }
  }
  const errEl = $("st-error");
  if (st.error) {
    errEl.textContent = st.error;
    errEl.classList.remove("hidden");
  } else {
    errEl.classList.add("hidden");
  }
  const busy = ["running", "login", "discover"].includes(st.state);
  const loginBtn = $("btn-open-login");
  const discoverBtn = $("btn-discover");
  if (loginBtn) loginBtn.disabled = busy;
  if (discoverBtn) discoverBtn.disabled = busy;
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const token = sessionStorage.getItem("mafibot_ui_token") || "";
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  ws = new WebSocket(`${proto}://${location.host}/ws${qs}`);
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "log") appendLog(msg.message, { fromServer: true });
      else if (msg.type === "status") {
        applyStatus(msg);
        if (msg.state === "completed" || msg.state === "stopped" || msg.state === "failed") {
          loadLastSessionMetrics();
        }
      }
    } catch (e) {
      console.warn(e);
    }
  };
  ws.onclose = () => {
    setTimeout(connectWs, 2000);
  };
}

async function loadHealth() {
  const h = await api("/api/health");
  const line = $("health-meta-line");
  if (line) {
    line.textContent = `v${h.version} · ${h.config_dir}`;
    line.title = `Config: ${h.config_dir}`;
  }
  const hint = $("cfg-dir-hint");
  if (hint) {
    hint.textContent = `Profiles dir: ${h.profiles_dir} · Browser profile: ${h.profile_dir}`;
  }
  const saveBtn = $("btn-save-profile");
  if (saveBtn) {
    saveBtn.title = hint?.textContent || "Save profile to disk";
  }
}

function formatKr(amount) {
  if (amount == null || Number.isNaN(amount)) return "—";
  return `${Number(amount).toLocaleString("nb-NO")} kr`;
}

function formatSessionWhen(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}

function formatSessionDuration(startIso, endIso) {
  if (!startIso || !endIso) return "—";
  const ms = new Date(endIso) - new Date(startIso);
  if (Number.isNaN(ms) || ms < 0) return "—";
  const totalMin = Math.round(ms / 60000);
  if (totalMin < 60) return `${totalMin} min`;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

function renderLastSessionMetrics(m) {
  const empty = $("last-session-empty");
  const table = $("last-session-table");
  const body = $("last-session-body");
  if (!empty || !table || !body) return;

  const showEmpty = (message) => {
    empty.textContent = message;
    empty.classList.remove("hidden");
    table.classList.add("hidden");
    body.replaceChildren();
  };

  const showTable = () => {
    empty.classList.add("hidden");
    table.classList.remove("hidden");
    body.replaceChildren();
  };

  if (!m) {
    showEmpty("No previous session recorded.");
    return;
  }

  showTable();

  const addRow = (label, value) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = label;
    const td = document.createElement("td");
    if (value instanceof Node) td.appendChild(value);
    else td.textContent = value;
    tr.append(th, td);
    body.appendChild(tr);
  };

  const pill = (text, kind) => {
    const span = document.createElement("span");
    span.className = `config-pill session-pill session-pill-${kind}`;
    span.textContent = text;
    return span;
  };

  const profileCell = document.createElement("span");
  profileCell.className = "last-session-profile";
  profileCell.textContent = m.profile || "—";
  if (m.dry_run) {
    profileCell.appendChild(document.createTextNode(" "));
    profileCell.appendChild(pill("Dry run", "muted"));
  }
  addRow("Profile", profileCell);
  addRow("Started", formatSessionWhen(m.started_at));
  addRow("Ended", formatSessionWhen(m.ended_at));
  addRow("Duration", formatSessionDuration(m.started_at, m.ended_at));

  const actions = document.createElement("span");
  actions.className = "config-overview-pills";
  actions.append(
    pill(`${m.actions_run} ok`, "ok"),
    pill(`${m.actions_failed} failed`, m.actions_failed ? "fail" : "muted"),
    pill(`${m.actions_skipped} idle`, "muted")
  );
  addRow("Actions", actions);

  if (m.money_start != null || m.money_end != null) {
    const money = document.createElement("span");
    money.className = "last-session-money";
    const delta =
      m.money_start != null && m.money_end != null ? m.money_end - m.money_start : null;
    money.textContent = `${formatKr(m.money_start)} → ${formatKr(m.money_end)}`;
    if (delta != null && delta !== 0) {
      const deltaEl = document.createElement("span");
      deltaEl.className = `last-session-delta ${delta > 0 ? "positive" : "negative"}`;
      deltaEl.textContent = ` (${delta > 0 ? "+" : ""}${formatKr(delta)})`;
      money.appendChild(deltaEl);
    }
    addRow("Money", money);
  }

  if (m.rank_start != null || m.rank_end != null) {
    addRow("Rank", `${m.rank_start ?? "—"} → ${m.rank_end ?? "—"}`);
  }

  if (m.hotel_time_percent != null) {
    addRow("Time in hotel", `${m.hotel_time_percent.toFixed(0)}%`);
  }

  const issues = [];
  if (m.parse_failures) issues.push(`${m.parse_failures} parse`);
  if (m.hotel_book_failures) issues.push(`${m.hotel_book_failures} hotel book`);
  if (issues.length) addRow("Issues", issues.join(" · "));

  if (m.stop_reason) {
    const stop = document.createElement("span");
    stop.className = "config-pill session-pill session-pill-stop";
    stop.textContent = m.stop_reason;
    addRow("Stopped", stop);
  }
}

async function loadLastSessionMetrics() {
  const empty = $("last-session-empty");
  if (!empty) return;

  const metricsPromise = api("/api/session/metrics").catch((e) => ({ error: e }));
  const historyPromise = api("/api/session/metrics/history?limit=12").catch((e) => ({
    error: e,
  }));

  const mResult = await metricsPromise;
  if (mResult?.error) {
    empty.classList.remove("hidden");
    $("last-session-table")?.classList.add("hidden");
    empty.textContent = `Could not load session: ${mResult.error.message}`;
  } else {
    try {
      renderLastSessionMetrics(mResult);
    } catch (e) {
      empty.classList.remove("hidden");
      $("last-session-table")?.classList.add("hidden");
      empty.textContent = `Could not display session: ${e.message}`;
    }
  }

  const hResult = await historyPromise;
  const list = $("session-history-list");
  if (!list) return;
  if (hResult?.error) {
    list.replaceChildren();
    const li = document.createElement("li");
    li.className = "cooldown-empty muted";
    li.textContent = `Could not load: ${hResult.error.message}`;
    list.appendChild(li);
    return;
  }
  const rows = Array.isArray(hResult) ? hResult : [];
  list.replaceChildren();
  if (!rows.length) {
    const li = document.createElement("li");
    li.className = "cooldown-empty muted";
    li.textContent = "No history yet";
    list.appendChild(li);
    return;
  }
  rows.forEach((row) => {
    const li = document.createElement("li");
    const money =
      row.money_start != null && row.money_end != null
        ? `${formatKr(row.money_start)} → ${formatKr(row.money_end)}`
        : "—";
    li.textContent = `${row.profile} · ${row.ended_at || row.started_at} · ${money}`;
    list.appendChild(li);
  });
}

async function loadPreflight() {
  const panel = $("preflight-panel");
  if (!panel) return;
  try {
    const pf = await api("/api/preflight");
    panel.replaceChildren();
    panel.classList.remove("hidden");
    const title = document.createElement("p");
    title.className = `preflight-title ${pf.ok ? "preflight-title--ok" : "preflight-title--fail"}`;
    title.textContent = pf.ok ? "Pre-flight: OK" : "Pre-flight: issues";
    panel.appendChild(title);
    pf.checks.forEach((c) => {
      const row = document.createElement("p");
      row.className = `preflight-check ${c.ok ? "preflight-check--ok" : "preflight-check--fail"}`;
      const icon = document.createElement("span");
      icon.className = "preflight-check-icon";
      icon.textContent = c.ok ? "✓" : "✗";
      const id = document.createElement("span");
      id.className = "preflight-check-id";
      id.textContent = c.id;
      const msg = document.createElement("span");
      msg.className = "preflight-check-msg";
      msg.textContent = c.message;
      row.append(icon, id, msg);
      panel.appendChild(row);
    });
    pf.warnings.forEach((w) => {
      const p = document.createElement("p");
      p.className = "preflight-warn";
      const icon = document.createElement("span");
      icon.className = "preflight-warn-icon";
      icon.textContent = "⚠";
      p.append(icon, document.createTextNode(w));
      panel.appendChild(p);
    });
  } catch (e) {
    panel.replaceChildren();
    const p = document.createElement("p");
    p.className = "preflight-error";
    p.textContent = `Pre-flight unavailable: ${e.message}`;
    panel.appendChild(p);
    panel.classList.remove("hidden");
  }
}

function profileLabel(item) {
  if (item.deletable) {
    return item.is_bundled ? `${item.name} (customized)` : item.name;
  }
  return `${item.name} (built-in)`;
}

function currentProfileMeta() {
  const name = $("cfg-profile-select").value;
  return profileCatalog.find((p) => p.name === name) || null;
}

function updateProfileBadge() {
  const meta = currentProfileMeta();
  const badge = $("cfg-profile-badge");
  const delBtn = $("btn-profile-delete");
  if (!meta) {
    badge.textContent = "—";
    badge.className = "badge idle";
    delBtn.disabled = true;
    return;
  }
  $("cfg-profile-name").value = meta.name;
  if (meta.deletable) {
    badge.textContent = meta.is_bundled ? "customized" : "custom";
    badge.className = "badge completed";
    delBtn.disabled = false;
  } else {
    badge.textContent = "built-in";
    badge.className = "badge idle";
    delBtn.disabled = true;
  }
}

async function loadProfiles(selectName = null) {
  profileCatalog = await api("/api/profiles");
  const keep = selectName || $("cfg-profile-select").value;
  for (const sel of [$("run-profile"), $("cfg-profile-select")]) {
    sel.innerHTML = "";
    profileCatalog.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item.name;
      opt.textContent = profileLabel(item);
      sel.appendChild(opt);
    });
  }
  if (keep && profileCatalog.some((p) => p.name === keep)) {
    $("cfg-profile-select").value = keep;
    $("run-profile").value = keep;
  }
  updateProfileBadge();
}

function isValidProfileName(name) {
  return /^[a-zA-Z0-9_-]+$/.test(name);
}

async function saveCurrentProfile() {
  const selected = $("cfg-profile-select").value;
  const targetName = $("cfg-profile-name").value.trim();
  if (!isValidProfileName(targetName)) {
    throw new Error("Name must use letters, numbers, underscore, or hyphen only.");
  }
  const payload = profilePayload();
  const warnings = window.MafibotConfigPanel?.collectConfigWarnings(payload) || [];
  window.MafibotConfigPanel?.showValidationBanner(warnings);
  if (warnings.some((w) => w.includes("No actions enabled"))) {
    throw new Error(warnings.join(" "));
  }
  payload.name = targetName;
  if (targetName !== selected) {
    await api(`/api/profiles/${encodeURIComponent(selected)}/rename`, {
      method: "POST",
      body: JSON.stringify({ new_name: targetName }),
    });
  }
  await api(`/api/profiles/${encodeURIComponent(targetName)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  await loadProfiles(targetName);
  await loadProfileForm(targetName);
  appendLog(`Profile saved: ${targetName}`);
}

function profileToEnabledActionOrder(doc) {
  const order = [...(doc.economy_order || [])];
  const seen = new Set(order);
  const add = (id) => {
    if (!seen.has(id)) {
      order.push(id);
      seen.add(id);
    }
  };
  if (doc.social_enabled) {
    add("messages");
    add("family");
  }
  if (doc.combat_enabled) {
    add("murder");
  }
  if (doc.minions_enabled) add("minions");
  if (doc.missions_enabled) add("missions");
  if (doc.organized_crime_enabled) add("organized_crime");
  if (doc.market_enabled) add("market");
  return order;
}

function showActionHelp(actionId) {
  const meta = ACTION_CATALOG.find((a) => a.id === actionId);
  if (!meta) return;
  $("action-help-title").textContent = meta.label;
  $("action-help-body").textContent = meta.description;
  const dialog = $("action-help-dialog");
  if (typeof dialog.showModal === "function") {
    dialog.showModal();
  } else {
    alert(`${meta.label}\n\n${meta.description}`);
  }
}

function isActionEnabledInUI(actionId) {
  const li = $("cfg-action-list").querySelector(`.action-list-item[data-action="${actionId}"]`);
  if (!li) return false;
  const box = li.querySelector("[data-action-check]");
  return box && box.checked;
}

function ensureTravelForDrugs() {
  const list = $("cfg-action-list");
  const drugsLi = list.querySelector('.action-list-item[data-action="drugs"]');
  const travelLi = list.querySelector('.action-list-item[data-action="travel"]');
  if (!drugsLi || !travelLi) return;
  const drugsOn = drugsLi.querySelector("[data-action-check]").checked;
  const travelBox = travelLi.querySelector("[data-action-check]");
  if (drugsOn && !travelBox.checked) {
    travelBox.checked = true;
  }
  if (drugsOn && drugsLi.compareDocumentPosition(travelLi) & Node.DOCUMENT_POSITION_FOLLOWING) {
    list.insertBefore(travelLi, drugsLi);
  }
}

function getActionOptionsHost() {
  return $("action-options-host");
}

/** Park panels in the hidden host before the list is rebuilt. */
function stashActionOptionPanels() {
  const host = getActionOptionsHost();
  if (!host) return;
  for (const panelId of Object.values(ACTION_OPTION_PANELS)) {
    const panel = $(panelId);
    if (panel && panel.parentElement !== host) {
      host.appendChild(panel);
    }
  }
}

function mountActionOptionPanels() {
  const list = $("cfg-action-list");
  for (const [actionId, panelId] of Object.entries(ACTION_OPTION_PANELS)) {
    const li = list.querySelector(`.action-list-item[data-action="${actionId}"]`);
    const panel = $(panelId);
    const mount = li?.querySelector(".action-item-options-mount");
    if (li && panel && mount) {
      mount.appendChild(panel);
    }
  }
}

function setActionOptionsOpen(li, open) {
  const wrap = li?.querySelector(".action-item-options");
  const btn = li?.querySelector(".action-settings-btn");
  if (!wrap) return;
  wrap.classList.toggle("is-open", !!open);
  if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
}

function updateActionOptionsVisibility() {
  const list = $("cfg-action-list");
  for (const actionId of Object.keys(ACTION_OPTION_PANELS)) {
    const li = list.querySelector(`.action-list-item[data-action="${actionId}"]`);
    if (!li) continue;
    const on = isActionEnabledInUI(actionId);
    const wrap = li.querySelector(".action-item-options");
    const btn = li.querySelector(".action-settings-btn");
    if (wrap) {
      wrap.classList.toggle("hidden", !on);
      if (!on) setActionOptionsOpen(li, false);
    }
    if (btn) btn.disabled = !on;
  }
}

function renderActionList(enabledOrder) {
  stashActionOptionPanels();
  const list = $("cfg-action-list");
  list.innerHTML = "";
  const enabledSet = new Set(enabledOrder);
  const displayOrder = [];
  const seen = new Set();
  for (const id of enabledOrder) {
    if (ACTION_CATALOG.some((a) => a.id === id) && !seen.has(id)) {
      displayOrder.push(id);
      seen.add(id);
    }
  }
  for (const { id } of ACTION_CATALOG) {
    if (!seen.has(id)) {
      displayOrder.push(id);
    }
  }

  for (const id of displayOrder) {
    const meta = ACTION_CATALOG.find((a) => a.id === id);
    if (!meta) continue;
    const li = document.createElement("li");
    li.className = "action-list-item";
    li.dataset.action = id;
    const hasOptions = Object.prototype.hasOwnProperty.call(ACTION_OPTION_PANELS, id);
    li.innerHTML = `
      <div class="action-list-item-row">
        <label class="action-check">
          <input type="checkbox" data-action-check ${enabledSet.has(id) ? "checked" : ""} />
          <span>${meta.label}</span>
        </label>
        <div class="action-item-controls">
          ${
            hasOptions
              ? `<button type="button" class="action-settings-btn" data-action-settings="${id}" title="Settings" aria-label="Settings: ${meta.label}" aria-expanded="false">⚙</button>`
              : ""
          }
          <button type="button" class="action-help-btn" data-action-help="${id}" title="What does this do?" aria-label="Help: ${meta.label}">?</button>
          <div class="action-reorder">
            <button type="button" data-dir="up" title="Move up">↑</button>
            <button type="button" data-dir="down" title="Move down">↓</button>
          </div>
        </div>
      </div>
      ${
        hasOptions
          ? `<div class="action-item-options hidden"><div class="action-item-options-mount"></div></div>`
          : ""
      }
    `;
    list.appendChild(li);
  }
  mountActionOptionPanels();
  updateActionOptionsVisibility();
  ensureTravelForDrugs();
}

function getEnabledActionOrderFromUI() {
  return [...$("cfg-action-list").querySelectorAll(".action-list-item")]
    .filter((li) => li.querySelector("[data-action-check]").checked)
    .map((li) => li.dataset.action);
}

function moveActionItem(li, direction) {
  const list = $("cfg-action-list");
  if (direction === "up" && li.previousElementSibling) {
    list.insertBefore(li, li.previousElementSibling);
  } else if (direction === "down" && li.nextElementSibling) {
    list.insertBefore(li.nextElementSibling, li);
  }
}

function setupCrimeOptionsHandlers() {
  ensureCrimeUi();
}

function setupActionListHandlers() {
  $("cfg-action-list").addEventListener("change", (ev) => {
    if (ev.target.matches("[data-action-check]")) {
      updateActionOptionsVisibility();
      if (ev.target.closest('[data-action="drugs"]')) {
        ensureTravelForDrugs();
      }
    }
  });
  $("cfg-action-list").addEventListener("click", (ev) => {
    const settingsBtn = ev.target.closest(".action-settings-btn");
    if (settingsBtn) {
      ev.preventDefault();
      if (settingsBtn.disabled) return;
      const li = settingsBtn.closest(".action-list-item");
      const wrap = li?.querySelector(".action-item-options");
      if (wrap) {
        const open = !wrap.classList.contains("is-open");
        setActionOptionsOpen(li, open);
      }
      return;
    }
    const helpBtn = ev.target.closest("[data-action-help]");
    if (helpBtn) {
      ev.preventDefault();
      showActionHelp(helpBtn.dataset.actionHelp);
      return;
    }
    const btn = ev.target.closest("button[data-dir]");
    if (!btn) return;
    const li = btn.closest(".action-list-item");
    if (li) moveActionItem(li, btn.dataset.dir);
  });
}

function actionFlagsFromOrder(order) {
  const enabled = new Set(order);
  const marketMode = $("cfg-market-mode")?.value || "none";
  return {
    economy_order: order.filter((id) => ECONOMY_ACTION_IDS.has(id)),
    social_enabled: enabled.has("messages") || enabled.has("family"),
    combat_enabled: enabled.has("murder"),
    minions_enabled: enabled.has("minions"),
    missions_enabled: enabled.has("missions"),
    organized_crime_enabled: enabled.has("organized_crime"),
    market_enabled: enabled.has("market") && marketMode !== "none",
  };
}

function applyProfileDocument(doc) {
  $("cfg-build").value = doc.build || "ranker";
  if ($("cfg-scheduler")) $("cfg-scheduler").value = doc.scheduler || "priority";
  $("cfg-stay-in-hotel").checked = !!doc.stay_in_hotel;
  $("cfg-book-before").checked = !!doc.book_hotel_before_action;
  $("cfg-book-after").checked = !!doc.book_hotel_after_every_action;
  $("cfg-book-idle").checked = !!doc.book_hotel_when_idle;
  if ($("cfg-hotel-min-wallet")) $("cfg-hotel-min-wallet").value = doc.hotel_min_wallet ?? 500;
  if ($("cfg-hotel-max-cost")) $("cfg-hotel-max-cost").value = doc.hotel_max_nightly_cost ?? "";
  if ($("cfg-hotel-book-broke")) $("cfg-hotel-book-broke").checked = !!doc.hotel_book_when_broke;
  if ($("cfg-hotel-fallback")) $("cfg-hotel-fallback").checked = doc.hotel_fallback_when_blocked !== false;
  if ($("cfg-market-mode")) $("cfg-market-mode").value = doc.market_mode || "none";
  if ($("cfg-work-ready-only")) $("cfg-work-ready-only").checked = doc.work_only_when_ready !== false;
  $("cfg-max-book-sec").value = doc.max_seconds_before_book_hotel ?? 2;
  $("cfg-min-health").value = doc.min_health_percent ?? 35;
  $("cfg-jitter-min").value = doc.cooldown_jitter_min_sec ?? 30;
  $("cfg-jitter-max").value = doc.cooldown_jitter_max_sec ?? 120;
  $("cfg-click-min").value = doc.min_seconds_between_clicks ?? 2.8;
  $("cfg-tab-wait").value = doc.min_seconds_after_tab_change ?? 3.5;
  loadActionOptionsFromDoc(doc);
  renderActionList(profileToEnabledActionOrder(doc));
  window.MafibotConfigPanel?.loadExtendedProfileFields(doc);
}

async function loadProfileForm(name) {
  const doc = await api(`/api/profiles/${encodeURIComponent(name)}`);
  applyProfileDocument(doc);
  window.MafibotConfigPanel?.setConfigSnapshotFromPayload(profilePayload());
  window.MafibotConfigPanel?.renderConfigSummary(profilePayload());
  window.MafibotConfigPanel?.showValidationBanner(
    window.MafibotConfigPanel.collectConfigWarnings(profilePayload())
  );
}

function profilePayload() {
  const name = $("cfg-profile-name").value.trim() || $("cfg-profile-select").value;
  const actionOrder = getEnabledActionOrderFromUI();
  const flags = actionFlagsFromOrder(actionOrder);
  const base = {
    name,
    build: $("cfg-build").value,
    scheduler: $("cfg-scheduler")?.value || "priority",
    stay_in_hotel: $("cfg-stay-in-hotel").checked,
    book_hotel_before_action: $("cfg-book-before").checked,
    book_hotel_after_every_action: $("cfg-book-after").checked,
    book_hotel_when_idle: $("cfg-book-idle").checked,
    hotel_min_wallet: parseInt($("cfg-hotel-min-wallet")?.value, 10) || 500,
    hotel_max_nightly_cost: (() => {
      const v = $("cfg-hotel-max-cost")?.value.trim();
      return v ? parseInt(v, 10) : null;
    })(),
    hotel_book_when_broke: !!$("cfg-hotel-book-broke")?.checked,
    hotel_fallback_when_blocked: $("cfg-hotel-fallback")?.checked !== false,
    work_only_when_ready: $("cfg-work-ready-only")?.checked !== false,
    market_mode: $("cfg-market-mode")?.value || "none",
    max_seconds_before_book_hotel: parseFloat($("cfg-max-book-sec").value),
    min_health_percent: parseInt($("cfg-min-health").value, 10),
    cooldown_jitter_min_sec: parseFloat($("cfg-jitter-min").value),
    cooldown_jitter_max_sec: parseFloat($("cfg-jitter-max").value),
    min_seconds_between_clicks: parseFloat($("cfg-click-min").value),
    min_seconds_after_tab_change: parseFloat($("cfg-tab-wait").value),
    economy_order: flags.economy_order,
    social_enabled: flags.social_enabled,
    combat_enabled: flags.combat_enabled,
    minions_enabled: flags.minions_enabled,
    missions_enabled: flags.missions_enabled,
    organized_crime_enabled: flags.organized_crime_enabled,
    market_enabled: flags.market_enabled,
    market_mode: $("cfg-market-mode")?.value || "none",
  };
  const payload = appendActionOptionsToPayload(base);
  return window.MafibotConfigPanel
    ? window.MafibotConfigPanel.appendExtendedProfileFields(payload)
    : payload;
}

function applyCredentialsUi(st) {
  const configured = st.has_user && st.has_password;
  $("cred-form")?.classList.toggle("hidden", configured);
  $("cred-saved")?.classList.toggle("hidden", !configured);
  if (configured) {
    $("cred-saved-name").textContent = st.user || "—";
    $("cred-env-path").textContent = st.env_path;
    $("cred-user").value = st.user || "";
    return;
  }
  if (st.user) $("cred-user").value = st.user;
  const parts = [];
  if (st.has_user) parts.push("user set");
  if (st.has_password) parts.push("password set");
  $("cred-status").textContent = parts.length
    ? `${parts.join(", ")} · ${st.env_path}`
    : `No credentials saved · ${st.env_path}`;
}

async function loadCredentialsStatus() {
  const st = await api("/api/credentials");
  applyCredentialsUi(st);
}

async function refreshSession() {
  const s = await api("/api/session");
  $("session-logged-in").textContent = s.logged_in ? "yes" : "no";
  if (s.game) applyStatus({ ...lastStatus, game: s.game, state: lastStatus?.state || "idle" });
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $(`panel-${btn.dataset.tab}`).classList.add("active");
      const fab = document.querySelector(".config-save-fab");
      if (fab) {
        fab.setAttribute("aria-hidden", btn.dataset.tab === "config" ? "false" : "true");
      }
    });
  });
}

function setupActions() {
  $("btn-start-run").addEventListener("click", async () => {
    if (!$("run-accept-tos").checked) {
      alert("You must accept the ToS risk checkbox to start.");
      return;
    }
    try {
      await api("/api/run", {
        method: "POST",
        body: JSON.stringify({
          profile: $("run-profile").value,
          max_minutes: (() => {
            const v = $("run-max-minutes").value.trim();
            return v ? parseInt(v, 10) : null;
          })(),
          dry_run: $("run-dry-run").checked,
          headless: $("run-headless").checked,
          accept_tos: true,
          skip_preflight: $("run-skip-preflight")?.checked || false,
        }),
      });
      appendLog("Run started");
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-open-log")?.addEventListener("click", async () => {
    try {
      await api("/api/logs/open", { method: "POST" });
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-clear-log")?.addEventListener("click", async () => {
    if (!confirm("Clear saved log file?")) return;
    try {
      await api("/api/logs", { method: "DELETE" });
      $("log-output").replaceChildren();
      appendLog("Log cleared", { fromServer: true });
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-stop").addEventListener("click", async () => {
    try {
      await api("/api/stop", { method: "POST" });
      appendLog("Stop requested");
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-discover").addEventListener("click", async () => {
    if (!$("run-accept-tos").checked) {
      alert("Accept ToS checkbox is required for discovery.");
      return;
    }
    try {
      await api("/api/discover", {
        method: "POST",
        body: JSON.stringify({
          accept_tos: true,
          headless: $("run-headless").checked,
          compare_last: $("run-discover-compare")?.checked || false,
        }),
      });
      appendLog("Discovery started");
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-save-profile").addEventListener("click", async () => {
    try {
      await saveCurrentProfile();
    } catch (e) {
      alert(e.message);
    }
  });

  $("cfg-profile-select").addEventListener("change", () => {
    updateProfileBadge();
    loadProfileForm($("cfg-profile-select").value).catch((e) => alert(e.message));
  });

  $("btn-profile-new").addEventListener("click", async () => {
    const name = prompt("New profile name (letters, numbers, _ -):");
    if (!name) return;
    const stem = name.trim();
    if (!isValidProfileName(stem)) {
      alert("Invalid profile name.");
      return;
    }
    try {
      await api("/api/profiles", {
        method: "POST",
        body: JSON.stringify({ name: stem, copy_from: $("cfg-profile-select").value }),
      });
      await loadProfiles(stem);
      await loadProfileForm(stem);
      appendLog(`Created profile: ${stem}`);
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-profile-duplicate").addEventListener("click", async () => {
    const base = $("cfg-profile-select").value;
    const suggested = `${base}_copy`;
    const name = prompt(`Duplicate "${base}" as:`, suggested);
    if (!name) return;
    const stem = name.trim();
    if (!isValidProfileName(stem)) {
      alert("Invalid profile name.");
      return;
    }
    try {
      await api("/api/profiles", {
        method: "POST",
        body: JSON.stringify({ name: stem, copy_from: base }),
      });
      await loadProfiles(stem);
      await loadProfileForm(stem);
      appendLog(`Duplicated profile: ${stem}`);
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-profile-delete").addEventListener("click", async () => {
    const meta = currentProfileMeta();
    if (!meta?.deletable) return;
    const msg = meta.is_bundled
      ? `Remove your customized copy of "${meta.name}"? The built-in profile will remain.`
      : `Delete profile "${meta.name}" permanently?`;
    if (!confirm(msg)) return;
    try {
      await api(`/api/profiles/${encodeURIComponent(meta.name)}`, { method: "DELETE" });
      const fallback =
        profileCatalog.find((p) => p.name === "ranker")?.name || profileCatalog[0]?.name;
      await loadProfiles(fallback);
      if (fallback) await loadProfileForm(fallback);
      appendLog(`Deleted profile: ${meta.name}`);
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-save-creds").addEventListener("click", async () => {
    try {
      const st = await api("/api/credentials", {
        method: "PUT",
        body: JSON.stringify({
          user: $("cred-user").value,
          password: $("cred-pass").value,
        }),
      });
      $("cred-pass").value = "";
      applyCredentialsUi(st);
      appendLog("Credentials saved");
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-cred-logout")?.addEventListener("click", async () => {
    if (!confirm("Remove saved credentials from .env?")) return;
    try {
      const st = await api("/api/credentials", { method: "DELETE" });
      $("cred-user").value = "";
      $("cred-pass").value = "";
      applyCredentialsUi(st);
      appendLog("Credentials cleared");
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-open-login").addEventListener("click", async () => {
    try {
      await api("/api/login", { method: "POST", body: JSON.stringify({}) });
      appendLog("Login browser opening…");
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-login-done").addEventListener("click", async () => {
    try {
      await api("/api/login/done", { method: "POST" });
      appendLog("Closing login browser");
    } catch (e) {
      alert(e.message);
    }
  });

  $("btn-refresh-session").addEventListener("click", () => {
    refreshSession().catch((e) => alert(e.message));
  });

  $("btn-save-ui-token")?.addEventListener("click", () => {
    const v = $("ui-token")?.value.trim() || "";
    if (v) sessionStorage.setItem("mafibot_ui_token", v);
    else sessionStorage.removeItem("mafibot_ui_token");
    appendLog(v ? "UI token saved for this browser tab" : "UI token cleared");
    connectWs();
  });
}

async function init() {
  setupTabs();
  ensureTravelCityList();
  ensureCrimeUi();
  setupCrimeOptionsHandlers();
  setupActionListHandlers();
  setupActions();
  window.MafibotConfigPanel?.setupConfigPanelExtras();
  connectWs();
  await loadPersistedLogs();
  await loadHealth();
  await loadProfiles();
  const initial = $("run-profile").value || "ranker";
  await loadProfileForm(initial);
  await loadCredentialsStatus();
  const st = await api("/api/run/status");
  applyStatus(st);
  await loadLastSessionMetrics();
  await loadPreflight();
  const savedToken = sessionStorage.getItem("mafibot_ui_token");
  if (savedToken && $("ui-token")) $("ui-token").value = savedToken;
  setInterval(() => {
    tickCooldownCountdowns();
    if (lastStatus?.elapsed_sec != null && ["running", "login", "discover"].includes(lastStatus.state)) {
      applyStatus({ ...lastStatus, elapsed_sec: (lastStatus.elapsed_sec || 0) + 1 });
    }
  }, 1000);
}

init().catch((e) => {
  console.error(e);
  appendLog(`Init failed: ${e.message}`);
});
