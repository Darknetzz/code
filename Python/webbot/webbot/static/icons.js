/** Inline SVG icons for the Webbot dashboard (stroke style, currentColor). */

const _SVG =
  'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';

const ICONS = {
  play: `<svg ${_SVG}><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
  stop: `<svg ${_SVG}><rect x="6" y="6" width="12" height="12" rx="1"/></svg>`,
  help: `<svg ${_SVG}><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  helpSm: `<svg ${_SVG}><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  run: `<svg ${_SVG}><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
  builder: `<svg ${_SVG}><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
  plus: `<svg ${_SVG}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  tag: `<svg ${_SVG}><path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>`,
  save: `<svg ${_SVG}><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`,
  copy: `<svg ${_SVG}><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  import: `<svg ${_SVG}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
  export: `<svg ${_SVG}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 14 12 9 17 14"/><line x1="12" y1="9" x2="12" y2="21"/></svg>`,
  test: `<svg ${_SVG}><path d="M14.4 14.4 9.6 9.6"/><path d="M18.6 5.4a9 9 0 1 1-13.2 13.2"/><path d="m9 15 1.5-4.5L15 9l-4.5 1.5L9 15z"/></svg>`,
  chevronLeft: `<svg ${_SVG}><polyline points="15 18 9 12 15 6"/></svg>`,
  chevronRight: `<svg ${_SVG}><polyline points="9 18 15 12 9 6"/></svg>`,
  chevronUp: `<svg ${_SVG}><polyline points="18 15 12 9 6 15"/></svg>`,
  chevronDown: `<svg ${_SVG}><polyline points="6 9 12 15 18 9"/></svg>`,
  grip: `<svg ${_SVG}><circle cx="9" cy="5" r="1.25" fill="currentColor" stroke="none"/><circle cx="9" cy="12" r="1.25" fill="currentColor" stroke="none"/><circle cx="9" cy="19" r="1.25" fill="currentColor" stroke="none"/><circle cx="15" cy="5" r="1.25" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="1.25" fill="currentColor" stroke="none"/><circle cx="15" cy="19" r="1.25" fill="currentColor" stroke="none"/></svg>`,
  close: `<svg ${_SVG}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  trash: `<svg ${_SVG}><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`,
  discard: `<svg ${_SVG}><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>`,
  log: `<svg ${_SVG}><polyline points="4 17 10 11 14 15 20 9"/><line x1="4" y1="21" x2="20" y2="21"/></svg>`,
  python: `<svg ${_SVG}><path d="M12 2c-3 0-5 1.5-5 4v2h5v1H6c-2.5 0-4 1.8-4 4.5S3.5 18 6 18h2v-3c0-2.2 1.8-4 4-4h4c2.5 0 4-1.5 4-4s-1.5-4-5-4z"/><path d="M18 8h2c2.5 0 4 1.8 4 4.5S22.5 17 20 17h-2v-3c0-2.2-1.8-4-4-4"/></svg>`,
  json: `<svg ${_SVG}><path d="M8 3H7a2 2 0 0 0-2 2v2"/><path d="M8 21H7a2 2 0 0 1-2-2v-2"/><path d="M16 3h1a2 2 0 0 1 2 2v2"/><path d="M16 21h1a2 2 0 0 0 2-2v-2"/><path d="M9 9h1"/><path d="M9 15h1"/><path d="M14 9h1"/><path d="M14 15h1"/></svg>`,
  list: `<svg ${_SVG}><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>`,
  edit: `<svg ${_SVG}><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`,
  flows: `<svg ${_SVG}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
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

function initStaticIcons() {
  const buttons = [
    ["tab-workspace", "edit", { label: "Workspace" }],
    ["tab-groups", "flows", { label: "Flow groups" }],
    ["groups-back", "chevronLeft", { label: "Back to workspace" }],
    ["btn-help", "help"],
    ["btn-start", "play"],
    ["btn-stop", "stop"],
    ["btn-add-step", "plus", { label: "Add step" }],
    ["btn-save", "save", { label: "Save" }],
    ["btn-test-run", "test", { label: "Test run" }],
    ["btn-dup-json", "copy", { label: "Duplicate" }],
    ["btn-export-json", "export", { label: "Export" }],
    ["btn-import-json", "import", { label: "Import" }],
    ["btn-save-python", "save", { label: "Save Python flow" }],
    ["btn-test-run-python", "test", { label: "Test run" }],
    ["btn-dup-python", "copy", { label: "Duplicate" }],
    ["btn-export-python", "export", { label: "Export" }],
    ["btn-import-python", "import", { label: "Import" }],
    ["btn-new-flow", "plus", { label: "New flow" }],
    ["help-prev", "chevronLeft", { label: "Previous" }],
    ["help-next", "chevronRight", { label: "Next" }],
    ["help-close", "close", { label: "Close" }],
  ];
  for (const [id, name, opts] of buttons) {
    const el = document.getElementById(id);
    if (el) enhanceButton(el, name, opts || {});
  }

  document.querySelectorAll(".btn-delete-flow").forEach((el) => {
    const label = el.textContent.trim() || "Delete";
    enhanceButton(el, "trash", { label });
  });

  document.querySelectorAll(".btn-discard-flow-changes").forEach((el) => {
    const label = el.textContent.trim() || "Discard changes";
    enhanceButton(el, "discard", { label });
  });

  const logTitle = document.querySelector(".log-card h2");
  if (logTitle && !logTitle.querySelector(".icon")) {
    logTitle.classList.add("heading-with-icon");
    logTitle.prepend(icon("log", "icon icon-heading"));
  }

  const stepsHeader = document.querySelector(".steps-header h2");
  if (stepsHeader && !stepsHeader.querySelector(".icon")) {
    stepsHeader.classList.add("heading-with-icon");
    stepsHeader.prepend(icon("list", "icon icon-heading"));
  }

}

function makeIconButton(iconName, label, onClick, options = {}) {
  const btn = document.createElement("button");
  btn.type = "button";
  enhanceButton(btn, iconName, { iconOnly: true, label });
  if (options.danger) btn.classList.add("danger");
  if (options.success) btn.classList.add("success", "outline");
  if (onClick) btn.addEventListener("click", onClick);
  return btn;
}

document.addEventListener("DOMContentLoaded", initStaticIcons);
