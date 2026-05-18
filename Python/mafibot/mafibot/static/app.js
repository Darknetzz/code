const $ = (id) => document.getElementById(id);

/** All gameplay actions the brain can schedule (hotel handled separately). */
const ACTION_CATALOG = [
  {
    id: "crime",
    label: "Crime (Kriminalitet)",
    description:
      "Opens the Kriminalitet tab and runs a crime when the cooldown is ready. Leaves the hotel first (crime is blocked in hotel), then returns to hotel after.",
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
      "Opens Mitt rederi in the sidebar and handles ship actions (send, depart) when the ship is ready or in port. Can run in the hotel.",
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
      "Opens the drugs page and buys/sells when controls are available. Must leave the hotel first.",
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
    id: "murder",
    label: "Murder (combat)",
    description:
      "Opens murder/skyt, fills a target username from your list, then shoots if aggression allows. Will not run without targets or with blank names. Must leave the hotel. High ban risk.",
  },
];

const ECONOMY_ACTION_IDS = new Set([
  "crime",
  "business",
  "ship",
  "travel",
  "drugs",
  "bank",
]);

let ws = null;
let elapsedTimer = null;
let lastStatus = null;
let profileCatalog = [];

function api(path, options = {}) {
  return fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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

function appendLog(message) {
  const el = $("log-output");
  const line = document.createElement("p");
  line.className = "log-line";
  line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function setBadge(state) {
  const badge = $("status-badge");
  badge.textContent = state || "idle";
  badge.className = `badge ${(state || "idle").toLowerCase()}`;
}

function applyStatus(st) {
  lastStatus = st;
  setBadge(st.state);
  $("st-profile").textContent = st.profile || "—";
  $("st-elapsed").textContent = formatElapsed(st.elapsed_sec);
  const g = st.game || {};
  $("st-hotel").textContent = g.in_hotel ? "yes" : "no";
  $("st-money").textContent = g.money != null ? String(g.money) : "—";
  $("st-health").textContent = g.health_percent != null ? `${g.health_percent}%` : "—";
  $("st-location").textContent = g.location || "—";
  $("st-crime").textContent = g.crime_ready ? "yes" : "no";
  $("st-action").textContent = st.last_action || "—";
  $("st-message").textContent = st.last_message || "—";
  const errEl = $("st-error");
  if (st.error) {
    errEl.textContent = st.error;
    errEl.classList.remove("hidden");
  } else {
    errEl.classList.add("hidden");
  }
  const busy = ["running", "login", "discover"].includes(st.state);
  $("btn-start-run").disabled = busy;
  $("btn-open-login").disabled = busy;
  $("btn-discover").disabled = busy;
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "log") appendLog(msg.message);
      else if (msg.type === "status") applyStatus(msg);
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
  $("health-version").textContent = `v${h.version}`;
  $("health-paths").textContent = `config: ${h.config_dir}`;
  $("cfg-dir-hint").textContent = `Profiles dir: ${h.profiles_dir} · Browser profile: ${h.profile_dir}`;
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

function renderActionList(enabledOrder) {
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
    li.innerHTML = `
      <label class="action-check">
        <input type="checkbox" data-action-check ${enabledSet.has(id) ? "checked" : ""} />
        <span>${meta.label}</span>
      </label>
      <div class="action-item-controls">
        <button type="button" class="action-help-btn" data-action-help="${id}" title="What does this do?" aria-label="Help: ${meta.label}">?</button>
        <div class="action-reorder">
          <button type="button" data-dir="up" title="Move up">↑</button>
          <button type="button" data-dir="down" title="Move down">↓</button>
        </div>
      </div>
    `;
    list.appendChild(li);
  }
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

function setupActionListHandlers() {
  $("cfg-action-list").addEventListener("click", (ev) => {
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
  return {
    economy_order: order.filter((id) => ECONOMY_ACTION_IDS.has(id)),
    social_enabled: enabled.has("messages") || enabled.has("family"),
    combat_enabled: enabled.has("murder"),
  };
}

async function loadProfileForm(name) {
  const doc = await api(`/api/profiles/${encodeURIComponent(name)}`);
  $("cfg-build").value = doc.build || "ranker";
  $("cfg-stay-in-hotel").checked = !!doc.stay_in_hotel;
  $("cfg-book-before").checked = !!doc.book_hotel_before_action;
  $("cfg-book-after").checked = !!doc.book_hotel_after_every_action;
  $("cfg-book-idle").checked = !!doc.book_hotel_when_idle;
  $("cfg-max-book-sec").value = doc.max_seconds_before_book_hotel ?? 2;
  $("cfg-min-health").value = doc.min_health_percent ?? 35;
  $("cfg-jitter-min").value = doc.cooldown_jitter_min_sec ?? 30;
  $("cfg-jitter-max").value = doc.cooldown_jitter_max_sec ?? 120;
  $("cfg-click-min").value = doc.min_seconds_between_clicks ?? 2.8;
  $("cfg-tab-wait").value = doc.min_seconds_after_tab_change ?? 3.5;
  $("cfg-bank-auto").checked = !!doc.bank_auto_balance;
  $("cfg-bank-keep").value = doc.bank_keep_cash_on_hand ?? 100000;
  $("cfg-bank-tolerance").value = doc.bank_balance_tolerance ?? 25000;
  $("cfg-murder-targets").value = (doc.murder_targets || []).join("\n");
  $("cfg-murder-rotate").checked = !!doc.murder_rotate_targets;
  renderActionList(profileToEnabledActionOrder(doc));
}

function profilePayload() {
  const name = $("cfg-profile-name").value.trim() || $("cfg-profile-select").value;
  const actionOrder = getEnabledActionOrderFromUI();
  const flags = actionFlagsFromOrder(actionOrder);
  return {
    name,
    build: $("cfg-build").value,
    stay_in_hotel: $("cfg-stay-in-hotel").checked,
    book_hotel_before_action: $("cfg-book-before").checked,
    book_hotel_after_every_action: $("cfg-book-after").checked,
    book_hotel_when_idle: $("cfg-book-idle").checked,
    max_seconds_before_book_hotel: parseFloat($("cfg-max-book-sec").value),
    min_health_percent: parseInt($("cfg-min-health").value, 10),
    cooldown_jitter_min_sec: parseFloat($("cfg-jitter-min").value),
    cooldown_jitter_max_sec: parseFloat($("cfg-jitter-max").value),
    min_seconds_between_clicks: parseFloat($("cfg-click-min").value),
    min_seconds_after_tab_change: parseFloat($("cfg-tab-wait").value),
    economy_order: flags.economy_order,
    social_enabled: flags.social_enabled,
    combat_enabled: flags.combat_enabled,
    bank_auto_balance: $("cfg-bank-auto").checked,
    bank_keep_cash_on_hand: parseInt($("cfg-bank-keep").value, 10) || 0,
    bank_balance_tolerance: parseInt($("cfg-bank-tolerance").value, 10) || 0,
    murder_targets: $("cfg-murder-targets").value
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
    murder_rotate_targets: $("cfg-murder-rotate").checked,
  };
}

async function loadCredentialsStatus() {
  const st = await api("/api/credentials");
  const parts = [];
  if (st.has_user) parts.push("user set");
  if (st.has_password) parts.push("password set");
  $("cred-status").textContent = parts.length
    ? `${parts.join(", ")} · ${st.env_path}`
    : `No credentials saved · ${st.env_path}`;
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
          max_minutes: parseInt($("run-max-minutes").value, 10) || null,
          dry_run: $("run-dry-run").checked,
          headless: $("run-headless").checked,
          accept_tos: true,
        }),
      });
      appendLog("Run started");
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
        body: JSON.stringify({ accept_tos: true, headless: $("run-headless").checked }),
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
      await api("/api/credentials", {
        method: "PUT",
        body: JSON.stringify({
          user: $("cred-user").value,
          password: $("cred-pass").value,
        }),
      });
      $("cred-pass").value = "";
      await loadCredentialsStatus();
      appendLog("Credentials saved");
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
}

async function init() {
  setupTabs();
  setupActionListHandlers();
  setupActions();
  connectWs();
  await loadHealth();
  await loadProfiles();
  const initial = $("run-profile").value || "ranker";
  await loadProfileForm(initial);
  await loadCredentialsStatus();
  const st = await api("/api/run/status");
  applyStatus(st);
  setInterval(() => {
    if (lastStatus?.elapsed_sec != null && ["running", "login", "discover"].includes(lastStatus.state)) {
      applyStatus({ ...lastStatus, elapsed_sec: (lastStatus.elapsed_sec || 0) + 1 });
    }
  }, 1000);
}

init().catch((e) => {
  console.error(e);
  appendLog(`Init failed: ${e.message}`);
});
