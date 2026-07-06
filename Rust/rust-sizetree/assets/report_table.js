<script>
(function () {
  var table = document.getElementById("pytree-items");
  if (!table) return;
  var tbody = table.querySelector("tbody");
  if (!tbody) return;

  // ---------- Build an index of the flat row list ----------
  // Every row is a direct child of <tbody>; parent-child relationships live
  // on data-path / data-parent. We index once and reuse for sort / expand /
  // filter so we never re-query the DOM.
  var rows = Array.prototype.slice.call(tbody.querySelectorAll(":scope > tr.item-row"));
  var byPath = Object.create(null);
  var childrenOf = Object.create(null);
  var topRows = [];
  rows.forEach(function (r) {
    var p = r.getAttribute("data-path");
    var par = r.getAttribute("data-parent") || "";
    byPath[p] = r;
    (childrenOf[par] = childrenOf[par] || []).push(r);
    if (!par) topRows.push(r);
  });

  // ---------- Expand / collapse ----------
  function directChildren(row) {
    return childrenOf[row.getAttribute("data-path")] || [];
  }
  function setExpanded(row, open) {
    var btn = row.querySelector(".row-expand");
    if (!btn) return;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      directChildren(row).forEach(function (ch) { ch.hidden = false; });
    } else {
      // Recursively hide and collapse every descendant.
      var stack = directChildren(row).slice();
      while (stack.length) {
        var r = stack.pop();
        r.hidden = true;
        var b = r.querySelector(".row-expand");
        if (b) b.setAttribute("aria-expanded", "false");
        Array.prototype.push.apply(stack, directChildren(r));
      }
    }
  }

  table.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".row-expand");
    if (!btn || !table.contains(btn)) return;
    var row = btn.closest("tr.item-row");
    if (!row) return;
    var open = btn.getAttribute("aria-expanded") !== "true";
    setExpanded(row, open);
  });

  // ---------- Sorting ----------
  var headers = table.querySelectorAll("thead th[data-sort-key]");
  var current = { key: "size", dir: "desc" };
  var foldersFirstCb = document.getElementById("folders-first-cb");

  function clearSortMarks() {
    headers.forEach(function (th) { th.classList.remove("sort-asc", "sort-desc"); });
  }

  function cmp(a, b, key, dir) {
    if (foldersFirstCb && foldersFirstCb.checked) {
      var ka = parseInt(a.getAttribute("data-kind") || "0", 10);
      var kb = parseInt(b.getAttribute("data-kind") || "0", 10);
      if (ka !== kb) return ka - kb; // 0 = dir, 1 = file → dirs first
    }
    var mul = dir === "asc" ? 1 : -1;
    if (key === "name") {
      var na = a.getAttribute("data-sort-name") || "";
      var nb = b.getAttribute("data-sort-name") || "";
      if (na !== nb) {
        return mul * na.localeCompare(nb, undefined, { numeric: true, sensitivity: "base" });
      }
    } else {
      var ak = key === "pct" ? "data-pct" : "data-" + key;
      var va = parseFloat(a.getAttribute(ak) || "0");
      var vb = parseFloat(b.getAttribute(ak) || "0");
      if (va !== vb) return mul * (va - vb);
    }
    var fa = a.getAttribute("data-sort-name") || "";
    var fb = b.getAttribute("data-sort-name") || "";
    return fa.localeCompare(fb, undefined, { numeric: true, sensitivity: "base" });
  }

  // Return every descendant of `row` in depth-first document order, so that
  // when we reorder top-level rows their whole subtree moves with them.
  function subtree(row) {
    var out = [];
    var stack = directChildren(row).slice().reverse();
    while (stack.length) {
      var r = stack.pop();
      out.push(r);
      var kids = directChildren(r);
      for (var i = kids.length - 1; i >= 0; i--) stack.push(kids[i]);
    }
    return out;
  }

  function applySort(key, toggle) {
    if (toggle) {
      if (current.key === key) {
        current.dir = current.dir === "asc" ? "desc" : "asc";
      } else {
        current.key = key;
        current.dir = key === "name" ? "asc" : "desc";
      }
    }
    clearSortMarks();
    var th = table.querySelector('thead th[data-sort-key="' + current.key + '"]');
    if (th) th.classList.add(current.dir === "asc" ? "sort-asc" : "sort-desc");

    var sorted = topRows.slice().sort(function (a, b) {
      return cmp(a, b, current.key, current.dir);
    });
    var frag = document.createDocumentFragment();
    sorted.forEach(function (row, i) {
      var idx = row.querySelector(".col-idx");
      if (idx) idx.textContent = String(i + 1);
      frag.appendChild(row);
      subtree(row).forEach(function (r) { frag.appendChild(r); });
    });
    tbody.appendChild(frag);
  }

  headers.forEach(function (th) {
    th.addEventListener("click", function () {
      applySort(th.getAttribute("data-sort-key"), true);
    });
  });
  if (foldersFirstCb) {
    foldersFirstCb.addEventListener("change", function () { applySort(current.key, false); });
  }
  applySort("size", false);

  // ---------- Expand-all / Collapse-all ----------
  var expandBtn = document.getElementById("tree-expand-all");
  var collapseBtn = document.getElementById("tree-collapse-all");
  if (expandBtn) {
    expandBtn.addEventListener("click", function () {
      rows.forEach(function (r) {
        if (r.getAttribute("data-has-kids") === "1") {
          var b = r.querySelector(".row-expand");
          if (b) b.setAttribute("aria-expanded", "true");
        }
        if (r.getAttribute("data-depth") !== "0") r.hidden = false;
      });
    });
  }
  if (collapseBtn) {
    collapseBtn.addEventListener("click", function () {
      rows.forEach(function (r) {
        var b = r.querySelector(".row-expand");
        if (b) b.setAttribute("aria-expanded", "false");
        if (r.getAttribute("data-depth") !== "0") r.hidden = true;
      });
    });
  }

  // ---------- Filter (top-level by name) ----------
  var filterInput = document.getElementById("tree-filter");
  var filterStatus = document.getElementById("tree-filter-status");
  if (filterInput) {
    function applyFilter() {
      var q = (filterInput.value || "").trim().toLowerCase();
      var shown = 0;
      topRows.forEach(function (row) {
        var name = (row.getAttribute("data-sort-name") || "").toLowerCase();
        var match = !q || name.indexOf(q) !== -1;
        row.classList.toggle("row-hidden", !match);
        // Hide the whole subtree when filtered out; leave expansion state alone.
        subtree(row).forEach(function (r) { r.classList.toggle("row-hidden", !match); });
        if (match) shown += 1;
      });
      if (filterStatus) {
        filterStatus.textContent = q
          ? shown + " of " + topRows.length + " match"
          : "";
      }
    }
    filterInput.addEventListener("input", applyFilter);
    filterInput.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { filterInput.value = ""; applyFilter(); }
    });
  }
})();
</script>