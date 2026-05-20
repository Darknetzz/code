/** Config tab: extended profile fields, validation, presets, import/export. */
(function () {
  const MARKET_ITEM_OPTIONS = [
    { id: "våpen", label: "Våpen" },
    { id: "kuler", label: "Kuler" },
    { id: "bil", label: "Bil" },
  ];

  const MINION_TRAINING_OPTIONS = [
    { id: "angrep", label: "Angrep" },
    { id: "beskyttelse", label: "Beskyttelse" },
    { id: "intelligens", label: "Intelligens" },
  ];

  let minionsRoster = [];

  const travelRotateInputs = new Map();
  let travelRotateBuilt = false;
  const marketBuyInputs = new Map();
  const marketSellInputs = new Map();
  let marketItemsBuilt = false;

  let configSnapshotJson = "";
  let configDirty = false;

  function $c(id) {
    return document.getElementById(id);
  }

  function ensureTravelRotatePool() {
    const container = $c("cfg-travel-rotate-pool");
    if (!container || travelRotateBuilt) return;
    travelRotateBuilt = true;
    for (const city of GAME_CITIES) {
      const slug = city.value.replace(/\s+/g, "-").toLowerCase();
      const id = `cfg-rotate-city-${slug}`;
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = city.value;
      input.id = id;
      travelRotateInputs.set(city.value, input);
      label.htmlFor = id;
      label.appendChild(input);
      label.append(document.createTextNode(city.label));
      container.appendChild(label);
    }
  }

  function ensureMarketItemLists() {
    if (marketItemsBuilt) return;
    marketItemsBuilt = true;
    const buy = $c("cfg-market-buy-items");
    const sell = $c("cfg-market-sell-items");
    for (const item of MARKET_ITEM_OPTIONS) {
      for (const [container, map] of [
        [buy, marketBuyInputs],
        [sell, marketSellInputs],
      ]) {
        if (!container) continue;
        const slug = item.id.replace(/[^\w]/g, "");
        const id = `cfg-market-${container.id}-${slug}`;
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = item.id;
        input.id = id;
        map.set(item.id, input);
        label.htmlFor = id;
        label.appendChild(input);
        label.append(document.createTextNode(item.label));
        container.appendChild(label);
      }
    }
  }

  function loadMarketItemsFromDoc(buyList, sellList) {
    ensureMarketItemLists();
    const buy = new Set((buyList || []).map(String));
    const sell = new Set((sellList || []).map(String));
    for (const [id, input] of marketBuyInputs) input.checked = buy.has(id);
    for (const [id, input] of marketSellInputs) input.checked = sell.has(id);
  }

  function getMarketItemsFromUi(map) {
    return [...map.entries()].filter(([, inp]) => inp.checked).map(([id]) => id);
  }

  function loadTravelRotatePoolFromDoc(selected) {
    ensureTravelRotatePool();
    const want = new Set((selected || []).map((s) => String(s).trim()).filter(Boolean));
    for (const [value, input] of travelRotateInputs) {
      input.checked = want.has(value);
    }
  }

  function getTravelRotatePoolFromUi() {
    ensureTravelRotatePool();
    return GAME_CITIES.filter((c) => travelRotateInputs.get(c.value)?.checked).map(
      (c) => c.value
    );
  }

  function updateMinionsSummary(scan) {
    const el = $c("cfg-minions-summary");
    if (!el) return;
    if (!scan || !scan.total) {
      el.textContent = "Undersåtter: — (refresh from game while logged in)";
      return;
    }
    el.textContent = `Undersåtter: ${scan.total} total (${scan.alive} alive, ${scan.dead} dead)`;
  }

  function renderMinionsRoster(minions, trainingMap) {
    const container = $c("cfg-minions-roster");
    if (!container) return;
    container.replaceChildren();
    const list = minions || [];
    if (!list.length) {
      const p = document.createElement("p");
      p.className = "tos-note";
      p.textContent = "No minions listed. Refresh from game while logged in.";
      container.appendChild(p);
      return;
    }
    const table = document.createElement("table");
    table.className = "minions-table";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const label of ["Name", "Status", "Treningstype"]) {
      const th = document.createElement("th");
      th.textContent = label;
      headRow.appendChild(th);
    }
    thead.appendChild(headRow);
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    const map = trainingMap || {};
    const defaultTrain = $c("cfg-minions-default-training")?.value || "angrep";
    for (const m of list) {
      const tr = document.createElement("tr");
      tr.dataset.minionName = m.name;
      const nameTd = document.createElement("td");
      nameTd.textContent = m.name;
      tr.appendChild(nameTd);
      const statusTd = document.createElement("td");
      statusTd.textContent = m.alive ? "Lever" : "Død";
      statusTd.className = m.alive ? "minion-alive" : "minion-dead";
      tr.appendChild(statusTd);
      const trainTd = document.createElement("td");
      if (m.alive) {
        const sel = document.createElement("select");
        sel.dataset.minionTraining = "1";
        const want = map[m.name] || m.training || defaultTrain;
        for (const opt of MINION_TRAINING_OPTIONS) {
          const o = document.createElement("option");
          o.value = opt.id;
          o.textContent = opt.label;
          if (opt.id === want) o.selected = true;
          sel.appendChild(o);
        }
        sel.addEventListener("change", () => markConfigDirty());
        trainTd.appendChild(sel);
      } else {
        trainTd.textContent = "—";
      }
      tr.appendChild(trainTd);
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    container.appendChild(table);
  }

  function loadMinionsFromDoc(doc) {
    const def = $c("cfg-minions-default-training");
    if (def) def.value = doc.minions_default_training || "angrep";
    const training = doc.minions_training || {};
    let list = minionsRoster;
    if (!list.length && Object.keys(training).length) {
      list = Object.keys(training).map((name) => ({
        name,
        alive: true,
        training: training[name],
      }));
    }
    renderMinionsRoster(list, training);
    if (list.length) {
      updateMinionsSummary({
        total: list.length,
        alive: list.filter((m) => m.alive).length,
        dead: list.filter((m) => !m.alive).length,
      });
    } else {
      updateMinionsSummary(null);
    }
  }

  function getMinionsTrainingFromUi() {
    const training = {};
    const container = $c("cfg-minions-roster");
    if (!container) return training;
    for (const row of container.querySelectorAll("tr[data-minion-name]")) {
      const name = row.dataset.minionName;
      const sel = row.querySelector("select[data-minion-training]");
      if (name && sel?.value) training[name] = sel.value;
    }
    return training;
  }

  async function refreshMinionsFromGame() {
    const btn = $c("btn-minions-refresh");
    if (btn) btn.disabled = true;
    try {
      const scan = await api("/api/minions/scan");
      minionsRoster = scan.minions || [];
      const training = getMinionsTrainingFromUi();
      const def = $c("cfg-minions-default-training")?.value || "angrep";
      for (const m of minionsRoster) {
        if (m.alive && !training[m.name]) {
          training[m.name] = m.training || def;
        }
      }
      renderMinionsRoster(minionsRoster, training);
      updateMinionsSummary(scan);
      markConfigDirty();
      appendLog(
        `Undersåtter: ${scan.total} (${scan.alive} alive, ${scan.dead} dead)`
      );
    } catch (e) {
      alert(e.message || String(e));
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function webhookUrlFromUi() {
    const notify = $c("cfg-stop-webhook-notify");
    return (notify?.value || "").trim();
  }

  function assistWebhookUrlFromUi() {
    const assist = $c("cfg-assist-webhook-notify");
    return (assist?.value || "").trim();
  }

  function setWebhookUrlInUi(stopUrl, assistUrl) {
    const notify = $c("cfg-stop-webhook-notify");
    if (notify) notify.value = stopUrl || "";
    const assist = $c("cfg-assist-webhook-notify");
    if (assist) assist.value = assistUrl || "";
  }

  function loadExtendedProfileFields(doc) {
    const ag = $c("cfg-aggression");
    if (ag) ag.value = doc.aggression ?? 0.3;
    updateAggressionLabel();
    if ($c("cfg-scheduler-happy-hour")) {
      $c("cfg-scheduler-happy-hour").checked = doc.scheduler_happy_hour_boost !== false;
    }
    if ($c("cfg-scheduler-city-income")) {
      $c("cfg-scheduler-city-income").checked = doc.scheduler_city_income_boost !== false;
    }
    if ($c("cfg-max-session-minutes")) {
      $c("cfg-max-session-minutes").value = doc.max_session_minutes ?? 120;
    }
    if ($c("cfg-play-start")) {
      $c("cfg-play-start").value = doc.play_window?.start_hour ?? 8;
    }
    if ($c("cfg-play-end")) {
      $c("cfg-play-end").value = doc.play_window?.end_hour ?? 23;
    }
    if ($c("cfg-idle-chance")) $c("cfg-idle-chance").value = doc.idle_chance ?? 0.1;
    if ($c("cfg-idle-min")) $c("cfg-idle-min").value = doc.idle_min_minutes ?? 5;
    if ($c("cfg-idle-max")) $c("cfg-idle-max").value = doc.idle_max_minutes ?? 15;
    if ($c("cfg-post-wait-min")) {
      $c("cfg-post-wait-min").value = doc.post_action_wait_min_sec ?? 8;
    }
    if ($c("cfg-post-wait-max")) {
      $c("cfg-post-wait-max").value = doc.post_action_wait_max_sec ?? 25;
    }
    if ($c("cfg-nothing-wait-min")) {
      $c("cfg-nothing-wait-min").value = doc.nothing_todo_wait_min_sec ?? 45;
    }
    if ($c("cfg-nothing-wait-max")) {
      $c("cfg-nothing-wait-max").value = doc.nothing_todo_wait_max_sec ?? 180;
    }
    if ($c("cfg-pause-restricted")) {
      $c("cfg-pause-restricted").checked = doc.pause_on_restricted_status !== false;
    }
    setWebhookUrlInUi(doc.stop_webhook_url || "", doc.assist_webhook_url || "");
    if ($c("cfg-assist-war")) $c("cfg-assist-war").checked = !!doc.assist_webhook_on_war;
    if ($c("cfg-assist-kidnap")) $c("cfg-assist-kidnap").checked = !!doc.assist_webhook_on_kidnap;
    if ($c("cfg-minions-train-when-ready")) {
      $c("cfg-minions-train-when-ready").checked = doc.minions_train_when_ready !== false;
    }
    minionsRoster = [];
    loadMinionsFromDoc(doc);
    if ($c("cfg-missions-auto-start")) {
      $c("cfg-missions-auto-start").checked = doc.missions_auto_start !== false;
    }
    if ($c("cfg-missions-prioritize")) {
      $c("cfg-missions-prioritize").checked = doc.missions_prioritize_when_incomplete !== false;
    }
    const orgHp = $c("cfg-org-crime-min-health");
    if (orgHp) {
      orgHp.value =
        doc.organized_crime_min_health_percent != null
          ? doc.organized_crime_min_health_percent
          : "";
    }
    if ($c("cfg-market-max-hour")) {
      $c("cfg-market-max-hour").value = doc.market_max_per_hour ?? 4;
    }
    if ($c("cfg-market-mission-buy")) {
      $c("cfg-market-mission-buy").checked = doc.market_buy_when_mission_needs !== false;
    }
    loadMarketItemsFromDoc(doc.market_buy_items, doc.market_sell_items);
    if ($c("cfg-travel-rotate")) $c("cfg-travel-rotate").checked = !!doc.travel_rotate_cities;
    if ($c("cfg-travel-rotate-min")) {
      $c("cfg-travel-rotate-min").value = doc.travel_rotate_min_minutes ?? 45;
    }
    loadTravelRotatePoolFromDoc(doc.travel_city_pool);
    if ($c("cfg-murder-travel")) {
      $c("cfg-murder-travel").checked = doc.murder_travel_before_shoot !== false;
    }
    if ($c("cfg-murder-attack-margin")) {
      $c("cfg-murder-attack-margin").value = doc.murder_min_attack_margin ?? 0;
    }
    updateMurderTargetsVisibility();
    syncRunTabFromProfile(doc);
  }

  function appendExtendedProfileFields(payload) {
    payload.aggression = parseFloat($c("cfg-aggression")?.value || "0.3");
    payload.scheduler_happy_hour_boost = !!$c("cfg-scheduler-happy-hour")?.checked;
    payload.scheduler_city_income_boost = !!$c("cfg-scheduler-city-income")?.checked;
    payload.max_session_minutes =
      parseInt($c("cfg-max-session-minutes")?.value, 10) || 120;
    payload.play_window = {
      start_hour: parseInt($c("cfg-play-start")?.value, 10) || 8,
      end_hour: parseInt($c("cfg-play-end")?.value, 10) || 23,
    };
    payload.idle_chance = parseFloat($c("cfg-idle-chance")?.value || "0.1");
    payload.idle_min_minutes = parseFloat($c("cfg-idle-min")?.value || "5");
    payload.idle_max_minutes = parseFloat($c("cfg-idle-max")?.value || "15");
    payload.post_action_wait_min_sec = parseFloat($c("cfg-post-wait-min")?.value || "8");
    payload.post_action_wait_max_sec = parseFloat($c("cfg-post-wait-max")?.value || "25");
    payload.nothing_todo_wait_min_sec = parseFloat(
      $c("cfg-nothing-wait-min")?.value || "45"
    );
    payload.nothing_todo_wait_max_sec = parseFloat(
      $c("cfg-nothing-wait-max")?.value || "180"
    );
    payload.pause_on_restricted_status = !!$c("cfg-pause-restricted")?.checked;
    payload.stop_webhook_url = webhookUrlFromUi();
    payload.assist_webhook_url = assistWebhookUrlFromUi();
    payload.assist_webhook_on_war = !!$c("cfg-assist-war")?.checked;
    payload.assist_webhook_on_kidnap = !!$c("cfg-assist-kidnap")?.checked;
    payload.minions_train_when_ready = !!$c("cfg-minions-train-when-ready")?.checked;
    payload.minions_default_training =
      $c("cfg-minions-default-training")?.value || "angrep";
    payload.minions_training = getMinionsTrainingFromUi();
    payload.missions_auto_start = !!$c("cfg-missions-auto-start")?.checked;
    payload.missions_prioritize_when_incomplete = !!$c("cfg-missions-prioritize")?.checked;
    const orgHpRaw = $c("cfg-org-crime-min-health")?.value.trim();
    payload.organized_crime_min_health_percent = orgHpRaw
      ? parseInt(orgHpRaw, 10)
      : null;
    payload.market_max_per_hour = parseInt($c("cfg-market-max-hour")?.value, 10) ?? 4;
    payload.market_buy_when_mission_needs = !!$c("cfg-market-mission-buy")?.checked;
    payload.market_buy_items = getMarketItemsFromUi(marketBuyInputs);
    payload.market_sell_items = getMarketItemsFromUi(marketSellInputs);
    payload.travel_rotate_cities = !!$c("cfg-travel-rotate")?.checked;
    payload.travel_rotate_min_minutes =
      parseInt($c("cfg-travel-rotate-min")?.value, 10) || 45;
    payload.travel_city_pool = getTravelRotatePoolFromUi();
    payload.murder_travel_before_shoot = !!$c("cfg-murder-travel")?.checked;
    payload.murder_min_attack_margin =
      parseInt($c("cfg-murder-attack-margin")?.value, 10) || 0;
    return payload;
  }

  function updateAggressionLabel() {
    const ag = $c("cfg-aggression");
    const lab = $c("cfg-aggression-value");
    if (ag && lab) lab.textContent = Number(ag.value).toFixed(2);
  }

  function updateMurderTargetsVisibility() {
    const wrap = $c("cfg-murder-targets-wrap");
    const mode = $c("cfg-murder-mode")?.value || "static_targets";
    if (wrap) wrap.classList.toggle("hidden", mode === "retaliate_only");
  }

  function syncRunTabFromProfile(doc) {
    const hint = $c("run-max-minutes-hint");
    const def = doc?.max_session_minutes ?? 120;
    if (hint) hint.textContent = `Leave empty to use profile default (${def} min).`;
    const input = $c("run-max-minutes");
    if (input) input.placeholder = String(def);
  }

  function collectConfigWarnings(payload) {
    const warnings = [];
    const order = getEnabledActionOrderFromUI();
    const enabled = new Set(order);
    const jitterMin = payload.cooldown_jitter_min_sec;
    const jitterMax = payload.cooldown_jitter_max_sec;
    if (jitterMin > jitterMax) {
      warnings.push("Cooldown jitter min is greater than max.");
    }
    if (enabled.has("murder")) {
      if (payload.murder_mode === "static_targets" && payload.aggression < 0.5) {
        warnings.push("Murder enabled but aggression is below 0.5 (static targets will not run).");
      }
      if (
        payload.murder_mode === "static_targets" &&
        (!payload.murder_targets || !payload.murder_targets.length)
      ) {
        warnings.push("Murder static-targets mode has no target usernames.");
      }
    }
    if (enabled.has("drugs")) {
      const travelIdx = order.indexOf("travel");
      const drugsIdx = order.indexOf("drugs");
      if (travelIdx === -1) {
        warnings.push("Drugs enabled but Travel is not in the action list.");
      } else if (drugsIdx !== -1 && travelIdx > drugsIdx) {
        warnings.push("Travel should appear before Drugs in the action list.");
      }
    }
    if (
      payload.scheduler === "soonest_ready" &&
      payload.nothing_todo_wait_max_sec > 300
    ) {
      warnings.push("Long nothing-to-do waits with soonest_ready may idle often.");
    }
    if (!order.length) {
      warnings.push("No actions enabled in the list.");
    }
    return warnings;
  }

  function actionLabel(id) {
    if (typeof ACTION_LABEL_BY_ID !== "undefined" && ACTION_LABEL_BY_ID[id]) {
      return ACTION_LABEL_BY_ID[id];
    }
    if (typeof ACTION_CATALOG !== "undefined") {
      const meta = ACTION_CATALOG.find((a) => a.id === id);
      if (meta) return meta.label;
    }
    return String(id).replace(/_/g, " ");
  }

  function pill(text, on) {
    const span = document.createElement("span");
    span.className = `config-pill${on ? " on" : " off"}`;
    span.textContent = text;
    return span;
  }

  function renderConfigSummary(payload) {
    const body = $c("cfg-summary-body");
    if (!body) return;

    body.replaceChildren();

    const order =
      typeof getEnabledActionOrderFromUI === "function"
        ? getEnabledActionOrderFromUI()
        : payload.economy_order || [];

    const addRow = (label, value) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.scope = "row";
      th.textContent = label;
      const td = document.createElement("td");
      if (value instanceof Node) {
        td.appendChild(value);
      } else {
        td.textContent = value;
      }
      tr.append(th, td);
      body.appendChild(tr);
    };

    addRow("Spesialisering", "In-game only");
    addRow("Scheduler", payload.scheduler || "—");

    if (!order.length) {
      addRow("Actions", "(none enabled)");
    } else {
      const ol = document.createElement("ol");
      ol.className = "config-overview-actions";
      order.forEach((id, index) => {
        const li = document.createElement("li");
        const step = document.createElement("span");
        step.className = "config-overview-step";
        step.textContent = String(index + 1);
        const name = document.createElement("span");
        name.textContent = actionLabel(id);
        li.append(step, name);
        ol.appendChild(li);
      });
      addRow("Actions", ol);
    }

    if (!payload.combat_enabled) {
      addRow("Skyt", "Off");
    } else {
      const mode = payload.murder_mode || "—";
      const targets = (payload.murder_targets || []).length;
      const detail =
        mode === "static_targets" ? `${mode} · ${targets} target${targets === 1 ? "" : "s"}` : mode;
      addRow("Skyt", detail);
    }

    addRow("Aggression", Number(payload.aggression ?? 0).toFixed(2));
    addRow("Session", `${payload.max_session_minutes ?? "—"} min`);
    const pw = payload.play_window;
    addRow(
      "Play window",
      pw ? `${pw.start_hour}:00 – ${pw.end_hour}:00` : "—"
    );

    addRow("Safety", pill("Hotel-first", !!payload.stay_in_hotel));

    const boosts = document.createElement("span");
    boosts.className = "config-overview-pills";
    boosts.append(
      pill("Happy Hour", !!payload.scheduler_happy_hour_boost),
      pill("City income", !!payload.scheduler_city_income_boost)
    );
    addRow("Boosts", boosts);
    addRow("Social", payload.social_enabled ? "Messages, Family" : "Off");

    if (payload.market_enabled && payload.market_mode && payload.market_mode !== "none") {
      addRow("Market", payload.market_mode);
    }

    const preview = $c("cfg-json-preview");
    if (preview) {
      const json = JSON.stringify(payload, null, 2);
      if (typeof setJsonPreview === "function") {
        setJsonPreview(preview, json);
      } else {
        preview.textContent = json;
      }
    }
  }

  function showValidationBanner(warnings) {
    const banner = $c("cfg-validation-banner");
    if (!banner) return;
    if (!warnings.length) {
      banner.classList.add("hidden");
      banner.replaceChildren();
      return;
    }
    banner.classList.remove("hidden");
    banner.replaceChildren();
    const list = document.createElement("ul");
    list.className = "config-validation-list";
    for (const w of warnings) {
      const li = document.createElement("li");
      li.textContent = w;
      list.appendChild(li);
    }
    banner.appendChild(list);
  }

  function setConfigSnapshotFromPayload(payload) {
    configSnapshotJson = JSON.stringify(payload);
    configDirty = false;
    updateConfigTabDirtyIndicator();
  }

  function markConfigDirty() {
    if (!configSnapshotJson) return;
    try {
      const current = JSON.stringify(profilePayload());
      configDirty = current !== configSnapshotJson;
    } catch {
      configDirty = true;
    }
    updateConfigTabDirtyIndicator();
    try {
      renderConfigSummary(profilePayload());
      showValidationBanner(collectConfigWarnings(profilePayload()));
    } catch {
      /* form incomplete */
    }
  }

  function updateConfigTabDirtyIndicator() {
    const tab = document.querySelector('.tab-btn[data-tab="config"]');
    if (tab) {
      const label = configDirty ? "Config *" : "Config";
      if (typeof setButtonLabel === "function") {
        setButtonLabel(tab, label);
      } else {
        tab.textContent = label;
      }
    }
    const saveBtn = document.getElementById("btn-save-profile");
    if (saveBtn) {
      saveBtn.disabled = !configDirty;
      saveBtn.classList.toggle("config-save-fab-btn--dirty", configDirty);
      const saveLabel = configDirty ? "Save changes" : "Save profile";
      if (typeof setButtonLabel === "function") {
        setButtonLabel(saveBtn, saveLabel);
      } else {
        saveBtn.textContent = saveLabel;
      }
      saveBtn.title = configDirty
        ? "Write unsaved profile changes to disk"
        : "No unsaved changes";
    }
  }

  function setupConfigPanelExtras() {
    ensureTravelRotatePool();
    ensureMarketItemLists();

    $c("cfg-aggression")?.addEventListener("input", () => {
      updateAggressionLabel();
      markConfigDirty();
    });
    $c("cfg-murder-mode")?.addEventListener("change", () => {
      updateMurderTargetsVisibility();
      markConfigDirty();
    });
    $c("cfg-minions-default-training")?.addEventListener("change", () =>
      markConfigDirty()
    );
    $c("btn-minions-refresh")?.addEventListener("click", () => {
      refreshMinionsFromGame();
    });

    document.querySelectorAll(".preset-row [data-preset]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const preset = btn.dataset.preset;
        if (!preset) return;
        try {
          const doc = await api(`/api/profiles/${encodeURIComponent(preset)}`);
          const name = $c("cfg-profile-name")?.value.trim() || $c("cfg-profile-select")?.value;
          const merged = { ...doc, name };
          applyProfileDocToForm(merged);
          markConfigDirty();
          appendLog(`Loaded preset: ${preset} (save to keep)`);
        } catch (e) {
          alert(e.message);
        }
      });
    });

    $c("btn-export-profile")?.addEventListener("click", () => {
      const payload = profilePayload();
      const text = JSON.stringify(payload, null, 2);
      navigator.clipboard.writeText(text).then(
        () => appendLog("Profile JSON copied to clipboard"),
        () => {
          const preview = $c("cfg-json-preview");
          if (preview && typeof setJsonPreview === "function") {
            setJsonPreview(preview, text);
          } else if (preview) {
            preview.textContent = text;
          }
          appendLog("Copy failed — see JSON preview");
        }
      );
    });

    $c("btn-import-profile")?.addEventListener("click", async () => {
      const raw = prompt("Paste profile JSON:");
      if (!raw) return;
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        alert("Invalid JSON");
        return;
      }
      const name = $c("cfg-profile-name")?.value.trim() || $c("cfg-profile-select")?.value;
      data.name = name;
      applyProfileDocToForm(data);
      markConfigDirty();
      appendLog("Imported JSON into form (save to persist)");
    });

    const panel = $c("panel-config");
    panel?.addEventListener("input", () => markConfigDirty());
    panel?.addEventListener("change", () => markConfigDirty());

    window.addEventListener("beforeunload", (ev) => {
      if (!configDirty) return;
      ev.preventDefault();
      ev.returnValue = "";
    });
  }

  function applyProfileDocToForm(doc) {
    if (typeof applyProfileDocument !== "function") return;
    applyProfileDocument(doc);
    try {
      const payload = profilePayload();
      renderConfigSummary(payload);
      showValidationBanner(collectConfigWarnings(payload));
    } catch {
      /* form incomplete */
    }
    markConfigDirty();
  }

  /** Called from app.js after defining loadProfileForm body */
  window.MafibotConfigPanel = {
    loadExtendedProfileFields,
    loadMinionsFromDoc,
    appendExtendedProfileFields,
    collectConfigWarnings,
    renderConfigSummary,
    showValidationBanner,
    setConfigSnapshotFromPayload,
    setupConfigPanelExtras,
    syncRunTabFromProfile,
    updateMurderTargetsVisibility,
  };
})();
