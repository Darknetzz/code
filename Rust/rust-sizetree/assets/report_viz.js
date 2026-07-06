<script>
(function () {
  var dataEl = document.getElementById("pytree-viz-data");
  if (!dataEl) return;
  var items = [];
  try { items = JSON.parse(dataEl.textContent || "[]"); } catch (e1) { return; }
  if (!items.length) return;

  var included = items.map(function () { return true; });
  var cx = 100, cy = 100, outerR = 78, innerR = 44;
  var pathG = document.getElementById("pytree-donut-paths");
  var hbar = document.getElementById("pytree-stacked-hbar");
  var donutEmpty = document.getElementById("pytree-donut-empty");
  var statusEl = document.getElementById("viz-filter-status");
  var tip = document.getElementById("pytree-viz-tooltip");
  var btnAll = document.getElementById("viz-show-all");
  var btnNone = document.getElementById("viz-hide-all");

  function htmlEscape(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function activeTotal() {
    var t = 0;
    items.forEach(function (it, i) { if (included[i]) t += it.size; });
    return t;
  }

  function highlightRow(idx) {
    clearRowHighlight();
    if (idx == null || isNaN(idx)) return;
    var rows = document.querySelectorAll(
      '#pytree-items tr.item-row[data-viz-idx="' + idx + '"]'
    );
    rows.forEach(function (r) { r.classList.add("viz-highlight"); });
  }
  function clearRowHighlight() {
    document
      .querySelectorAll("#pytree-items tr.item-row.viz-highlight")
      .forEach(function (r) { r.classList.remove("viz-highlight"); });
  }

  function bindSegEvents(nodes) {
    nodes.forEach(function (node) {
      node.addEventListener("mouseenter", function (e) {
        var idx = parseInt(node.getAttribute("data-viz-idx"), 10);
        showTip(e.clientX, e.clientY, idx);
        highlightRow(idx);
      });
      node.addEventListener("mousemove", function (e) {
        var idx = parseInt(node.getAttribute("data-viz-idx"), 10);
        showTip(e.clientX, e.clientY, idx);
      });
      node.addEventListener("mouseleave", function () {
        hideTip();
        clearRowHighlight();
      });
      node.addEventListener("click", function (e) {
        e.preventDefault();
        toggleIdx(parseInt(node.getAttribute("data-viz-idx"), 10));
      });
      node.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggleIdx(parseInt(node.getAttribute("data-viz-idx"), 10));
        }
      });
    });
  }

  function tooltipHtml(idx) {
    var it = items[idx];
    if (!it) return "";
    var tot = activeTotal();
    var pctChart = included[idx] && tot > 0 ? (100 * it.size / tot) : 0;
    var type = it.isDir ? "Directory" : "File";
    var lines = [
      "<strong>" + htmlEscape(it.name) + "</strong>",
      "Type: " + type,
      "Size: " + htmlEscape(it.human) + " (" + it.size.toLocaleString() + " bytes)"
    ];
    if (it.isDir) {
      lines.push("Files: " + it.files + " · Dirs: " + it.dirs);
    }
    lines.push(
      "Of scanned folder: " + (it.pctRoot != null ? it.pctRoot.toFixed(1) : "?") + "%"
    );
    if (included[idx] && tot > 0) {
      lines.push("Of visible chart: " + pctChart.toFixed(1) + "%");
    } else {
      lines.push("<em>Filtered out of chart</em>");
    }
    return lines.join("<br/>");
  }

  function showTip(x, y, idx) {
    if (!tip) return;
    tip.innerHTML = tooltipHtml(idx);
    tip.hidden = false;
    var tw = 300, th = tip.offsetHeight || 120;
    tip.style.left = Math.min(window.innerWidth - tw - 8, x + 12) + "px";
    tip.style.top = Math.min(window.innerHeight - th - 8, y + 12) + "px";
  }

  function hideTip() {
    if (tip) tip.hidden = true;
  }

  function buildDonutSvgPaths() {
    if (!pathG) return;
    var tot = activeTotal();
    if (tot <= 0) {
      pathG.innerHTML = "";
      return;
    }
    var start = -Math.PI / 2;
    var html = [];
    items.forEach(function (it, idx) {
      if (!included[idx] || it.size <= 0) return;
      var sweep = 2 * Math.PI * (it.size / tot);
      var a0 = start;
      var a1 = start + sweep;
      start = a1;
      var x0o = cx + outerR * Math.cos(a0), y0o = cy + outerR * Math.sin(a0);
      var x1o = cx + outerR * Math.cos(a1), y1o = cy + outerR * Math.sin(a1);
      var x0i = cx + innerR * Math.cos(a0), y0i = cy + innerR * Math.sin(a0);
      var x1i = cx + innerR * Math.cos(a1), y1i = cy + innerR * Math.sin(a1);
      var large = sweep > Math.PI ? 1 : 0;
      html.push(
        '<path class="viz-donut-seg" data-viz-idx="' + idx + '" tabindex="0" d="M ' + x0o.toFixed(2) + " " + y0o.toFixed(2) +
        " A " + outerR + " " + outerR + " 0 " + large + " 1 " + x1o.toFixed(2) + " " + y1o.toFixed(2) +
        " L " + x1i.toFixed(2) + " " + y1i.toFixed(2) +
        " A " + innerR + " " + innerR + " 0 " + large + " 0 " + x0i.toFixed(2) + " " + y0i.toFixed(2) +
        ' Z" fill="' + it.color + '" stroke="#0d1117" stroke-width="1"/>'
      );
    });
    pathG.innerHTML = html.join("");
    bindSegEvents(pathG.querySelectorAll(".viz-donut-seg"));
  }

  function buildHbar() {
    if (!hbar) return;
    var tot = activeTotal();
    hbar.innerHTML = "";
    if (tot <= 0) return;
    items.forEach(function (it, idx) {
      if (!included[idx]) return;
      var w = (100 * it.size) / tot;
      var span = document.createElement("span");
      span.className = "viz-hbar-seg";
      span.setAttribute("data-viz-idx", String(idx));
      span.style.width = w.toFixed(4) + "%";
      span.style.background = it.color;
      span.style.display = "block";
      span.style.height = "100%";
      span.style.minWidth = "2px";
      hbar.appendChild(span);
    });
    bindSegEvents(hbar.querySelectorAll(".viz-hbar-seg"));
  }

  function updateLegendPct() {
    var tot = activeTotal();
    var allOn = included.filter(Boolean).length === items.length;
    items.forEach(function (it, idx) {
      var row = document.querySelector('.viz-legend-row[data-viz-idx="' + idx + '"]');
      if (!row) return;
      var pctEl = row.querySelector(".legend-pct");
      if (!pctEl) return;
      if (included[idx] && tot > 0) {
        pctEl.textContent = ((100 * it.size) / tot).toFixed(1) + "%";
        pctEl.title = allOn
          ? "Share of scanned folder"
          : "Share of visible chart (of scan: " + it.pctRoot.toFixed(1) + "%)";
      } else {
        pctEl.textContent = it.pctRoot.toFixed(1) + "%";
        pctEl.title = "Share of scanned folder — hidden from chart";
      }
    });
  }

  function updateStatus() {
    var n = included.filter(Boolean).length;
    if (statusEl) {
      statusEl.textContent =
        n === items.length
          ? "Showing all " + items.length + " items in the chart."
          : "Showing " + n + " of " + items.length + " — donut and bar use only visible items.";
    }
    if (donutEmpty) donutEmpty.hidden = activeTotal() > 0;
    updateLegendPct();
  }

  function toggleIdx(idx) {
    if (idx < 0 || idx >= items.length) return;
    included[idx] = !included[idx];
    var cb = document.querySelector('.viz-filter-cb[data-viz-idx="' + idx + '"]');
    if (cb) cb.checked = included[idx];
    refresh();
  }

  function refresh() {
    buildDonutSvgPaths();
    buildHbar();
    updateStatus();
  }

  document.querySelectorAll(".viz-filter-cb").forEach(function (cb) {
    cb.addEventListener("change", function () {
      var idx = parseInt(cb.getAttribute("data-viz-idx"), 10);
      included[idx] = cb.checked;
      refresh();
    });
  });

  document.querySelectorAll(".viz-legend-row").forEach(function (row) {
    row.addEventListener("click", function (e) {
      if (e.target.tagName === "INPUT") return;
      var idx = parseInt(row.getAttribute("data-viz-idx"), 10);
      included[idx] = !included[idx];
      var c = row.querySelector(".viz-filter-cb");
      if (c) c.checked = included[idx];
      refresh();
    });
    row.addEventListener("mouseenter", function () {
      highlightRow(parseInt(row.getAttribute("data-viz-idx"), 10));
    });
    row.addEventListener("mouseleave", clearRowHighlight);
  });

  if (btnAll) {
    btnAll.addEventListener("click", function () {
      items.forEach(function (_, i) { included[i] = true; });
      document.querySelectorAll(".viz-filter-cb").forEach(function (cb) { cb.checked = true; });
      refresh();
    });
  }
  if (btnNone) {
    btnNone.addEventListener("click", function () {
      items.forEach(function (_, i) { included[i] = false; });
      document.querySelectorAll(".viz-filter-cb").forEach(function (cb) { cb.checked = false; });
      refresh();
    });
  }

  document.addEventListener("scroll", hideTip, true);
  window.addEventListener("blur", hideTip);

  bindSegEvents(document.querySelectorAll(".viz-donut-seg, .viz-hbar-seg"));
  updateStatus();
})();
</script>