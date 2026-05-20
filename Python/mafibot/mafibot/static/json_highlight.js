/** Minimal JSON syntax highlighting for the config preview panel. */

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function highlightJson(text) {
  if (!text || !String(text).trim()) {
    return '<span class="json-placeholder">Export to see JSON</span>';
  }
  const escaped = escapeHtml(String(text));
  return escaped.replace(
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
    (match, quoted, colon) => {
      if (colon) {
        return `<span class="json-key">${quoted}</span>:`;
      }
      if (quoted) {
        return `<span class="json-string">${quoted}</span>`;
      }
      if (match === "true" || match === "false") {
        return `<span class="json-bool">${match}</span>`;
      }
      if (match === "null") {
        return `<span class="json-null">${match}</span>`;
      }
      return `<span class="json-number">${match}</span>`;
    }
  );
}

function setJsonPreview(el, text) {
  if (!el) return;
  const raw = text == null ? "" : String(text);
  el.innerHTML = highlightJson(raw);
  el.dataset.rawJson = raw;
}

function getJsonPreviewText(el) {
  if (!el) return "";
  return el.dataset.rawJson ?? el.textContent ?? "";
}

window.setJsonPreview = setJsonPreview;
window.getJsonPreviewText = getJsonPreviewText;
