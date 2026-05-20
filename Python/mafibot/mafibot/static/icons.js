/** Inline SVG icons for the Mafibot dashboard (stroke style, currentColor). */

const _SVG =
  'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';

const ICONS = {
  play: `<svg ${_SVG}><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
  stop: `<svg ${_SVG}><rect x="6" y="6" width="12" height="12" rx="1"/></svg>`,
  discover: `<svg ${_SVG}><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>`,
  log: `<svg ${_SVG}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
  trash: `<svg ${_SVG}><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`,
  history: `<svg ${_SVG}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  plus: `<svg ${_SVG}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  copy: `<svg ${_SVG}><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  preset: `<svg ${_SVG}><path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`,
  export: `<svg ${_SVG}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 14 12 9 17 14"/><line x1="12" y1="9" x2="12" y2="21"/></svg>`,
  import: `<svg ${_SVG}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
  save: `<svg ${_SVG}><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`,
  logout: `<svg ${_SVG}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`,
  key: `<svg ${_SVG}><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.78 7.78 5.5 5.5 0 0 1 7.78-7.78zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>`,
  shield: `<svg ${_SVG}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
  browser: `<svg ${_SVG}><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
  check: `<svg ${_SVG}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  refresh: `<svg ${_SVG}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`,
  close: `<svg ${_SVG}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  help: `<svg ${_SVG}><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  settings: `<svg ${_SVG}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  chevronUp: `<svg ${_SVG}><polyline points="18 15 12 9 6 15"/></svg>`,
  chevronDown: `<svg ${_SVG}><polyline points="6 9 12 15 18 9"/></svg>`,
  tabRun: `<svg ${_SVG}><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
  tabSessions: `<svg ${_SVG}><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
  tabConfig: `<svg ${_SVG}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  tabLogin: `<svg ${_SVG}><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>`,
};

function icon(name, className = "icon") {
  const svg = ICONS[name];
  if (!svg) return document.createDocumentFragment();
  const span = document.createElement("span");
  span.className = className;
  span.setAttribute("aria-hidden", "true");
  span.innerHTML = svg;
  return span;
}

/**
 * @param {HTMLElement} button
 * @param {string} iconName
 * @param {{ label?: string, iconOnly?: boolean, small?: boolean }} [opts]
 */
function enhanceButton(button, iconName, opts = {}) {
  if (!button || button.dataset.iconEnhanced) return;
  const label = opts.label ?? button.textContent.trim();
  const iconClass = opts.small ? "icon icon-sm" : "icon";
  button.textContent = "";
  button.classList.add(opts.iconOnly ? "btn-icon-only" : "btn-with-icon");
  button.appendChild(icon(iconName, iconClass));
  if (!opts.iconOnly) {
    const span = document.createElement("span");
    span.className = "btn-label";
    span.textContent = label;
    button.appendChild(span);
  } else {
    button.setAttribute("aria-label", label);
  }
  button.dataset.iconEnhanced = "1";
}

/** Update label text without removing icon markup (for tabs/buttons enhanced earlier). */
function setButtonLabel(button, label) {
  if (!button) return;
  const labelEl = button.querySelector(".btn-label");
  if (labelEl) {
    labelEl.textContent = label;
    return;
  }
  button.textContent = label;
}

function initMafibotIcons() {
  const byId = [
    ["btn-start-run", "play", { label: "Start" }],
    ["btn-stop", "stop", { label: "Stop" }],
    ["btn-discover", "discover", { label: "Discover pages" }],
    ["btn-open-log", "log", { label: "Open log file", small: true }],
    ["btn-clear-log", "trash", { label: "Clear", small: true }],
    ["btn-session-show-latest", "history", { label: "Show latest saved", small: true }],
    ["btn-profile-new", "plus", { label: "New" }],
    ["btn-profile-duplicate", "copy", { label: "Duplicate" }],
    ["btn-profile-delete", "trash", { label: "Delete" }],
    ["btn-export-profile", "export", { label: "Export JSON" }],
    ["btn-import-profile", "import", { label: "Import JSON" }],
    ["btn-save-profile", "save", { label: "Save profile" }],
    ["btn-cred-logout", "logout", { label: "Log out" }],
    ["btn-save-creds", "save", { label: "Save credentials" }],
    ["btn-save-ui-token", "shield", { label: "Save UI token" }],
    ["btn-open-login", "browser", { label: "Open login browser" }],
    ["btn-login-done", "check", { label: "Done (close browser)" }],
    ["btn-refresh-session", "refresh", { label: "Refresh session" }],
  ];
  for (const [id, name, opts] of byId) {
    const el = document.getElementById(id);
    if (el) enhanceButton(el, name, opts);
  }

  document.querySelectorAll(".tab-btn[data-tab]").forEach((btn) => {
    const map = { run: "tabRun", sessions: "tabSessions", config: "tabConfig", login: "tabLogin" };
    const iconName = map[btn.dataset.tab];
    if (iconName) enhanceButton(btn, iconName, { label: btn.textContent.trim() });
  });

  document.querySelectorAll("button[data-preset]").forEach((btn) => {
    enhanceButton(btn, "preset", { label: btn.textContent.trim(), small: true });
  });

  const closeBtn = document.querySelector("#action-help-dialog button[type='submit']");
  if (closeBtn) enhanceButton(closeBtn, "close", { label: "Close" });
}

function enhanceActionListButtons(root = document) {
  root.querySelectorAll(".action-settings-btn").forEach((btn) => {
    enhanceButton(btn, "settings", { iconOnly: true, small: true, label: btn.getAttribute("aria-label") || "Settings" });
  });
  root.querySelectorAll(".action-help-btn").forEach((btn) => {
    enhanceButton(btn, "help", { iconOnly: true, small: true, label: btn.getAttribute("aria-label") || "Help" });
  });
  root.querySelectorAll(".action-reorder button[data-dir='up']").forEach((btn) => {
    enhanceButton(btn, "chevronUp", { iconOnly: true, small: true, label: "Move up" });
  });
  root.querySelectorAll(".action-reorder button[data-dir='down']").forEach((btn) => {
    enhanceButton(btn, "chevronDown", { iconOnly: true, small: true, label: "Move down" });
  });
}

function enhanceSessionHistoryButtons(root = document) {
  root.querySelectorAll("button.session-history-item").forEach((btn) => {
    if (btn.dataset.iconEnhanced) return;
    const head = btn.querySelector(".session-history-item-head");
    const meta = btn.querySelector(".session-history-item-meta");
    const label = head?.textContent?.trim() || "Session";
    btn.classList.add("btn-with-icon", "session-history-item--icon");
    const iconWrap = document.createElement("span");
    iconWrap.className = "icon icon-sm session-history-icon";
    iconWrap.setAttribute("aria-hidden", "true");
    iconWrap.innerHTML = ICONS.history;
    const body = document.createElement("span");
    body.className = "session-history-item-body";
    if (head) body.appendChild(head);
    if (meta) body.appendChild(meta);
    btn.textContent = "";
    btn.append(iconWrap, body);
    btn.dataset.iconEnhanced = "1";
    btn.setAttribute("aria-label", label);
  });
}
