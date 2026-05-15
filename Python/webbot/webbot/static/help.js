/** Help modal: single dialog with sidebar nav and prev/next. */

let _currentTopicId = "overview";
let _lastTrigger = null;

function _flatTopics() {
  return HELP_NAV.flatMap((g) => g.topics);
}

function _sectionForTopic(topicId) {
  return HELP_NAV.find((g) => g.topics.includes(topicId)) || HELP_NAV[0];
}

function _topicIndexInSection(topicId, section) {
  return section.topics.indexOf(topicId);
}

function _renderBody(topic) {
  const parts = Array.isArray(topic.body) ? topic.body : [topic.body];
  return parts.join("");
}

function createHelpButton(topicId) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "help-btn btn-icon-only";
  btn.setAttribute("aria-label", `Help: ${HELP_TOPICS[topicId]?.title || topicId}`);
  if (typeof icon === "function") {
    btn.appendChild(icon("helpSm", "icon icon-help-btn"));
  } else {
    btn.textContent = "?";
  }
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openHelp(topicId, btn);
  });
  return btn;
}

function _renderSidebar() {
  const nav = document.getElementById("help-nav");
  if (!nav) return;
  nav.innerHTML = "";

  const hint = document.createElement("p");
  hint.className = "help-nav-hint";
  hint.textContent = "Expand a section in the sidebar for detailed topics";
  nav.appendChild(hint);

  for (const group of HELP_NAV) {
    const details = document.createElement("details");
    details.className = "help-nav-group";
    const containsActive = group.topics.includes(_currentTopicId);
    if (containsActive) details.open = true;

    const summary = document.createElement("summary");
    summary.setAttribute("aria-label", `${group.label}, ${details.open ? "expanded" : "collapsed"}`);

    const title = document.createElement("span");
    title.className = "help-nav-group-title";
    title.textContent = group.label;

    const chevron = document.createElement("span");
    chevron.className = "help-nav-chevron";
    chevron.setAttribute("aria-hidden", "true");

    summary.appendChild(title);
    summary.appendChild(chevron);
    details.addEventListener("toggle", () => {
      summary.setAttribute(
        "aria-label",
        `${group.label}, ${details.open ? "expanded" : "collapsed"}`
      );
    });
    details.appendChild(summary);

    const ul = document.createElement("ul");
    for (const id of group.topics) {
      const topic = HELP_TOPICS[id];
      if (!topic) continue;
      const li = document.createElement("li");
      const link = document.createElement("button");
      link.type = "button";
      link.className = "help-nav-item";
      link.textContent = topic.title;
      link.dataset.topicId = id;
      if (id === _currentTopicId) {
        link.setAttribute("aria-current", "true");
      }
      link.addEventListener("click", () => {
        _showTopic(id);
      });
      li.appendChild(link);
      ul.appendChild(li);
    }
    details.appendChild(ul);
    nav.appendChild(details);
  }
}

function _updatePrevNext() {
  const section = _sectionForTopic(_currentTopicId);
  const idx = _topicIndexInSection(_currentTopicId, section);
  const prevBtn = document.getElementById("help-prev");
  const nextBtn = document.getElementById("help-next");
  if (prevBtn) {
    prevBtn.disabled = idx <= 0;
    prevBtn.onclick = () => {
      if (idx > 0) _showTopic(section.topics[idx - 1]);
    };
  }
  if (nextBtn) {
    nextBtn.disabled = idx < 0 || idx >= section.topics.length - 1;
    nextBtn.onclick = () => {
      if (idx < section.topics.length - 1) _showTopic(section.topics[idx + 1]);
    };
  }
}

function _showTopic(topicId) {
  const topic = HELP_TOPICS[topicId];
  if (!topic) {
    topicId = "overview";
  }
  _currentTopicId = topicId;
  const t = HELP_TOPICS[topicId];

  const titleEl = document.getElementById("help-title");
  const bodyEl = document.getElementById("help-body");
  const dialog = document.getElementById("help-dialog");

  if (titleEl) titleEl.textContent = t.title;
  if (bodyEl) bodyEl.innerHTML = _renderBody(t);
  if (dialog) dialog.setAttribute("aria-labelledby", "help-title");

  _renderSidebar();
  _updatePrevNext();

  const active = document.querySelector(`.help-nav-item[data-topic-id="${topicId}"]`);
  if (active) active.scrollIntoView({ block: "nearest" });
}

function openHelp(topicId, triggerEl = null) {
  if (!HELP_TOPICS[topicId]) topicId = "overview";
  _lastTrigger = triggerEl;
  _showTopic(topicId);
  const dialog = document.getElementById("help-dialog");
  if (dialog && !dialog.open) {
    dialog.showModal();
  }
}

function closeHelp() {
  const dialog = document.getElementById("help-dialog");
  if (dialog?.open) dialog.close();
  if (_lastTrigger && typeof _lastTrigger.focus === "function") {
    _lastTrigger.focus();
  }
  _lastTrigger = null;
}

function getActivePanelHelpTopic() {
  return "help.home";
}

function _attachPageHelpButton(el, topicId) {
  if (el.querySelector(".help-btn")) return;
  const btn = createHelpButton(topicId);
  const row = document.createElement("span");
  row.className = "label-row panel-help-row";
  if (el.classList.contains("section-heading") || el.tagName === "H2") {
    row.classList.add("section-heading-row");
  }
  el.parentNode.insertBefore(row, el);
  row.appendChild(el);
  row.appendChild(btn);
}

function bindPageHelpButtons() {
  document.querySelectorAll("[data-page-help]").forEach((el) => {
    const id = el.dataset.pageHelp;
    if (id) _attachPageHelpButton(el, id);
  });
}

function initHelp() {
  const dialog = document.getElementById("help-dialog");
  const closeBtn = document.getElementById("help-close");
  const headerBtn = document.getElementById("btn-help");

  if (closeBtn) closeBtn.addEventListener("click", closeHelp);

  if (dialog) {
    dialog.addEventListener("cancel", (e) => {
      e.preventDefault();
      closeHelp();
    });
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) closeHelp();
    });
  }

  if (headerBtn) {
    headerBtn.setAttribute("aria-label", "Help for workspace");
    headerBtn.addEventListener("click", () => openHelp(getActivePanelHelpTopic(), headerBtn));
  }

  bindPageHelpButtons();
}

document.addEventListener("DOMContentLoaded", initHelp);
