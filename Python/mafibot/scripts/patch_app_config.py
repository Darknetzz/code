"""Patch app.js for config panel integration."""
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "mafibot" / "static" / "app.js"
text = APP.read_text(encoding="utf-8")

# actionFlagsFromOrder
old = """function actionFlagsFromOrder(order) {
  const enabled = new Set(order);
  return {
    economy_order: order.filter((id) => ECONOMY_ACTION_IDS.has(id)),
    social_enabled: enabled.has("messages") || enabled.has("family"),
    combat_enabled: enabled.has("murder"),
    minions_enabled: !!$("cfg-minions-enabled")?.checked || enabled.has("minions"),
    missions_enabled: !!$("cfg-missions-enabled")?.checked || enabled.has("missions"),
    organized_crime_enabled:
      !!$("cfg-org-crime-enabled")?.checked || enabled.has("organized_crime"),
    market_enabled:
      !!$("cfg-market-enabled")?.checked ||
      (enabled.has("market") && ($("cfg-market-mode")?.value || "none") !== "none"),
  };
}"""

new = """function actionFlagsFromOrder(order) {
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
}"""

if old not in text:
    raise SystemExit("actionFlagsFromOrder block not found")
text = text.replace(old, new)

# profileToEnabledActionOrder
old = """  if (doc.combat_enabled) {
    add("murder");
  }
  return order;
}"""

new = """  if (doc.combat_enabled) {
    add("murder");
  }
  if (doc.minions_enabled) add("minions");
  if (doc.missions_enabled) add("missions");
  if (doc.organized_crime_enabled) add("organized_crime");
  if (doc.market_enabled) add("market");
  return order;
}"""

if old not in text:
    raise SystemExit("profileToEnabledActionOrder block not found")
text = text.replace(old, new)

# loadProfileForm - replace stop_webhook and remove enabled checkboxes lines, add applyProfileDocument
old = """async function loadProfileForm(name) {
  const doc = await api(`/api/profiles/${encodeURIComponent(name)}`);
  $("cfg-build").value = doc.build || "ranker";
  if ($("cfg-scheduler")) $("cfg-scheduler").value = doc.scheduler || "priority";
  if ($("cfg-stop-webhook")) $("cfg-stop-webhook").value = doc.stop_webhook_url || "";
  $("cfg-stay-in-hotel").checked = !!doc.stay_in_hotel;
  $("cfg-book-before").checked = !!doc.book_hotel_before_action;
  $("cfg-book-after").checked = !!doc.book_hotel_after_every_action;
  $("cfg-book-idle").checked = !!doc.book_hotel_when_idle;
  if ($("cfg-hotel-min-wallet")) $("cfg-hotel-min-wallet").value = doc.hotel_min_wallet ?? 500;
  if ($("cfg-hotel-max-cost")) $("cfg-hotel-max-cost").value = doc.hotel_max_nightly_cost ?? "";
  if ($("cfg-hotel-book-broke")) $("cfg-hotel-book-broke").checked = !!doc.hotel_book_when_broke;
  if ($("cfg-hotel-fallback")) $("cfg-hotel-fallback").checked = doc.hotel_fallback_when_blocked !== false;
  if ($("cfg-minions-enabled")) $("cfg-minions-enabled").checked = !!doc.minions_enabled;
  if ($("cfg-missions-enabled")) $("cfg-missions-enabled").checked = !!doc.missions_enabled;
  if ($("cfg-org-crime-enabled")) $("cfg-org-crime-enabled").checked = !!doc.organized_crime_enabled;
  if ($("cfg-market-enabled")) $("cfg-market-enabled").checked = !!doc.market_enabled;
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
}"""

new = """function applyProfileDocument(doc) {
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
}"""

if old not in text:
    raise SystemExit("loadProfileForm block not found")
text = text.replace(old, new)

# profilePayload - merge flags
old = """    economy_order: flags.economy_order,
    social_enabled: flags.social_enabled,
    combat_enabled: flags.combat_enabled,
  };
  return appendActionOptionsToPayload(base);
}"""

new = """    economy_order: flags.economy_order,
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
}"""

if old not in text:
    raise SystemExit("profilePayload block not found")
text = text.replace(old, new)

# saveCurrentProfile - validation
old = """async function saveCurrentProfile() {
  const selected = $("cfg-profile-select").value;
  const targetName = $("cfg-profile-name").value.trim();
  if (!isValidProfileName(targetName)) {
    throw new Error("Name must use letters, numbers, underscore, or hyphen only.");
  }
  const payload = profilePayload();"""

new = """async function saveCurrentProfile() {
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
  }"""

# run max minutes
old = """          max_minutes: parseInt($("run-max-minutes").value, 10) || null,"""
new = """          max_minutes: (() => {
            const v = $("run-max-minutes").value.trim();
            return v ? parseInt(v, 10) : null;
          })(),"""
text = text.replace(old, new)

# init - setup config panel
old = """  setupActions();
  connectWs();"""
new = """  setupActions();
  window.MafibotConfigPanel?.setupConfigPanelExtras();
  connectWs();"""
text = text.replace(old, new)

# config_panel applyProfileDocToForm
text = text.replace(
    "function applyProfileDocToForm(doc) {\n    loadProfileFormFromDoc(doc);\n  }",
    "function applyProfileDocToForm(doc) {\n    applyProfileDocument(doc);\n  }",
)

APP.write_text(text, encoding="utf-8")
print("patched app.js")
