"""Shared gallery pipeline used by ``pygallery.py`` and ``pygallery-snapchat.py``.

Exposes:
- :class:`FileInfo` plus media classification constants and helpers.
- :func:`make_file_info` / :func:`make_entry` to turn paths into manifest entries.
- :func:`build_stats`, :func:`print_summary`, :func:`write_outputs` for output.
- The static HTML / CSS / JS templates (data-driven tabs, configurable title).

Stdlib only.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".m4v"}
MEDIA_EXTS = IMG_EXTS | VIDEO_EXTS

KIND_MEDIA = "media"
KIND_THUMB = "thumbnail"
KIND_OVERLAY = "overlay"
KIND_METADATA = "metadata"
KIND_STANDALONE = "standalone"
KIND_OTHER = "other"

# "YYYY-MM-DD_rest" prefix (Snapchat style). We accept _, space, or - as sep.
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[_ -](.+)$")

# Phone camera style embedded date: IMG_YYYYMMDD_HHMMSS, VID_YYYYMMDD, etc.
CAMERA_DATE_RE = re.compile(r"(?:^|[_\- ])(\d{4})(\d{2})(\d{2})(?:[_\- ]\d{6})?")


# -----------------------------------------------------------------------------
# Data types
# -----------------------------------------------------------------------------


@dataclass
class FileInfo:
    path: Path
    rel: str           # URL-encoded path relative to gallery root
    date: str          # YYYY-MM-DD
    mtime: int         # seconds since epoch
    size: int
    ext: str           # lowercase including leading dot
    kind: str = KIND_STANDALONE
    folder: str = ""   # immediate parent folder name (display only)
    source: str = ""   # top-level grouping used for tabs


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def rel_url(p: Path, root: Path) -> str:
    """URL-safe path relative to ``root`` (forward slashes, percent-encoded)."""
    rel = p.relative_to(root).as_posix()
    return "/".join(urllib.parse.quote(seg) for seg in rel.split("/"))


def parse_date(name_stem: str, mtime: int) -> tuple[str, str]:
    """Return ``(YYYY-MM-DD, stem_after_date)``.

    Tries a ``YYYY-MM-DD`` prefix first, then an embedded ``YYYYMMDD`` typical
    of phone-camera filenames, and finally falls back to the file's ``mtime``.
    """
    m = DATE_RE.match(name_stem)
    if m:
        return m.group(1), m.group(2)

    cam = CAMERA_DATE_RE.search(name_stem)
    if cam:
        y, mo, d = cam.group(1), cam.group(2), cam.group(3)
        if 1990 <= int(y) <= 2100 and 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{mo}-{d}", name_stem

    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"), name_stem


def media_type(ext: str) -> str | None:
    if ext in IMG_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def make_file_info(p: Path, root: Path, *, kind: str = KIND_STANDALONE,
                   folder: str = "", source: str = "") -> FileInfo | None:
    """Build a :class:`FileInfo` for a path, or ``None`` if it cannot be stat'd."""
    try:
        st = p.stat()
    except OSError:
        return None
    mtime = int(st.st_mtime)
    date, _ = parse_date(p.stem, mtime)
    return FileInfo(
        path=p,
        rel=rel_url(p, root),
        date=date,
        mtime=mtime,
        size=st.st_size,
        ext=p.suffix.lower(),
        kind=kind,
        folder=folder,
        source=source,
    )


def make_entry(primary: FileInfo, *, thumb: FileInfo | None = None,
               overlay: FileInfo | None = None) -> dict | None:
    """Build a manifest entry for one displayable media file.

    Returns ``None`` if the extension isn't a recognized image or video.
    """
    mtype = media_type(primary.ext)
    if mtype is None:
        return None
    entry: dict = {
        "id": f"{primary.date}_{primary.path.stem[:48]}",
        "date": primary.date,
        "mtime": primary.mtime,
        "type": mtype,
        "source": primary.source,
        "folder": primary.folder,
        "media": primary.rel,
        "ext": primary.ext,
        "size": primary.size,
        "name": primary.path.name,
    }
    if thumb is not None:
        entry["thumb"] = thumb.rel
    if overlay is not None:
        entry["overlay"] = overlay.rel
    return entry


def build_stats(entries: list[dict], *, total_files: int, **extras) -> dict:
    """Aggregate counts by year / source / type from manifest entries."""
    stats: dict = {
        "total_files": total_files,
        "by_year": {},
        "by_source": {},
        "by_type": {"image": 0, "video": 0},
        **extras,
    }
    for e in entries:
        year = e["date"][:4]
        stats["by_year"][year] = stats["by_year"].get(year, 0) + 1
        src = e.get("source") or ""
        stats["by_source"][src] = stats["by_source"].get(src, 0) + 1
        stats["by_type"][e["type"]] += 1
    return stats


def print_summary(entries: list[dict], stats: dict, *, title: str,
                  out_html: Path, extras: dict | None = None) -> None:
    print(f"{title}: {len(entries)} items")
    print(f"  Files scanned:   {stats.get('total_files', 0)}")
    by_src = stats.get("by_source") or {}
    if by_src:
        label_w = max(len(k) or 6 for k in by_src)
        for src, n in sorted(by_src.items()):
            print(f"  {(src or '(root)').ljust(label_w)}: {n}")
    print(f"  Photos:          {stats['by_type']['image']}")
    print(f"  Videos:          {stats['by_type']['video']}")
    for k, v in (extras or {}).items():
        print(f"  {k}: {v}")
    if stats.get("by_year"):
        print("  By year:")
        for year in sorted(stats["by_year"].keys()):
            print(f"    {year}: {stats['by_year'][year]}")
    print(f"\nOpen: {out_html}")


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------


def _html_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


def write_outputs(entries: list[dict], stats: dict, *, root: Path,
                  title: str = "Gallery") -> Path:
    """Write ``gallery.html`` and ``gallery/`` assets into ``root``.

    Returns the path to the generated HTML file.
    """
    out_html = root / "gallery.html"
    out_dir = root / "gallery"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "entries": entries,
        "stats": stats,
        "title": title,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Inline the manifest so the page works over ``file://`` (no fetch needed).
    inlined = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    html = (HTML_TEMPLATE
            .replace("__TITLE__", _html_escape(title))
            .replace("__MANIFEST__", inlined))
    out_html.write_text(html, encoding="utf-8")
    (out_dir / "style.css").write_text(CSS, encoding="utf-8")
    (out_dir / "app.js").write_text(JS, encoding="utf-8")
    return out_html


# -----------------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------------


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="gallery/style.css">
</head>
<body>
<header class="topbar">
  <div class="title">
    <h1>__TITLE__</h1>
    <span id="countLabel" class="muted"></span>
  </div>
  <nav id="tabs" class="tabs" role="tablist"></nav>
  <div class="filters">
    <select id="yearFilter"><option value="">All years</option></select>
    <select id="monthFilter">
      <option value="">All months</option>
      <option value="01">Jan</option><option value="02">Feb</option>
      <option value="03">Mar</option><option value="04">Apr</option>
      <option value="05">May</option><option value="06">Jun</option>
      <option value="07">Jul</option><option value="08">Aug</option>
      <option value="09">Sep</option><option value="10">Oct</option>
      <option value="11">Nov</option><option value="12">Dec</option>
    </select>
    <select id="typeFilter">
      <option value="">All types</option>
      <option value="image">Photos</option>
      <option value="video">Videos</option>
    </select>
    <select id="sortFilter">
      <option value="desc">Newest first</option>
      <option value="asc">Oldest first</option>
    </select>
  </div>
</header>

<main id="grid" class="grid"></main>

<div id="lightbox" class="lightbox" hidden>
  <button class="lb-close" aria-label="Close">&times;</button>
  <button class="lb-prev" aria-label="Previous">&#8249;</button>
  <button class="lb-next" aria-label="Next">&#8250;</button>
  <div class="lb-stage"></div>
  <footer class="lb-meta"></footer>
</div>

<script>
window.MANIFEST = __MANIFEST__;
</script>
<script src="gallery/app.js"></script>
</body>
</html>
"""


CSS = r"""
:root {
  color-scheme: dark;
  --bg: #0b0b0d;
  --panel: #15151a;
  --panel-hi: #1e1e24;
  --text: #ececf1;
  --muted: #8a8a95;
  --accent: #fffc00;
  --accent-ink: #111;
  --border: #26262d;
  --shadow: 0 6px 24px rgba(0,0,0,.5);
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
  font-size: 14px;
  min-height: 100vh;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 18px;
  padding: 14px 20px;
  background: rgba(15,15,20,.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}
.title { display: flex; align-items: baseline; gap: 10px; margin-right: auto; }
.title h1 { font-size: 18px; margin: 0; font-weight: 600; letter-spacing: .2px; }
.muted { color: var(--muted); font-size: 12px; }

.tabs { display: flex; gap: 4px; padding: 3px; background: var(--panel); border-radius: 10px; border: 1px solid var(--border); }
.tabs:empty { display: none; }
.tab {
  appearance: none; border: 0; background: transparent; color: var(--muted);
  padding: 6px 12px; border-radius: 7px; cursor: pointer; font: inherit;
}
.tab:hover { color: var(--text); }
.tab.active { background: var(--accent); color: var(--accent-ink); font-weight: 600; }

.filters { display: flex; gap: 8px; flex-wrap: wrap; }
.filters select {
  appearance: none; background: var(--panel); color: var(--text);
  border: 1px solid var(--border); border-radius: 8px; padding: 6px 28px 6px 10px;
  font: inherit; cursor: pointer;
  background-image: linear-gradient(45deg, transparent 50%, var(--muted) 50%),
                    linear-gradient(135deg, var(--muted) 50%, transparent 50%);
  background-position: calc(100% - 14px) 50%, calc(100% - 9px) 50%;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px;
  padding: 12px;
}
.tile {
  position: relative;
  aspect-ratio: 1 / 1;
  background: var(--panel);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform .12s ease, box-shadow .12s ease;
}
.tile:hover { transform: translateY(-1px); box-shadow: var(--shadow); }
.tile img, .tile video {
  width: 100%; height: 100%; object-fit: cover; display: block;
  background: #000;
}
.tile .tile-overlay {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  object-fit: cover;
  pointer-events: none;
}
.tile .badge {
  position: absolute;
  top: 6px; left: 6px;
  background: rgba(0,0,0,.65);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  display: flex; gap: 4px; align-items: center;
  pointer-events: none;
}
.tile .badge.play { right: 6px; left: auto; background: rgba(0,0,0,.75); }
.tile .date {
  position: absolute;
  bottom: 6px; left: 6px; right: 6px;
  font-size: 11px;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,.8);
  pointer-events: none;
}

.empty {
  grid-column: 1 / -1;
  padding: 48px 12px;
  text-align: center;
  color: var(--muted);
}

/* Lightbox */
.lightbox[hidden] { display: none !important; }
.lightbox {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,.94);
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.lb-stage {
  position: relative;
  max-width: 95vw;
  max-height: calc(100vh - 80px);
  display: flex; align-items: center; justify-content: center;
}
.lb-stage img, .lb-stage video {
  max-width: 95vw;
  max-height: calc(100vh - 80px);
  display: block;
  border-radius: 4px;
  background: #000;
}
.lb-stage .lb-overlay {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  object-fit: contain;
  pointer-events: none;
}
.lb-meta {
  position: absolute;
  bottom: 10px; left: 50%;
  transform: translateX(-50%);
  color: var(--text);
  font-size: 13px;
  background: rgba(15,15,20,.8);
  border: 1px solid var(--border);
  padding: 8px 14px;
  border-radius: 8px;
  max-width: 90vw;
  text-align: center;
}
.lb-meta .muted { margin-left: 8px; }
.lb-close, .lb-prev, .lb-next {
  position: absolute;
  appearance: none; border: 0; background: rgba(255,255,255,.08);
  color: var(--text);
  width: 44px; height: 44px;
  border-radius: 50%;
  font-size: 22px; line-height: 1;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.lb-close:hover, .lb-prev:hover, .lb-next:hover { background: rgba(255,255,255,.18); }
.lb-close { top: 14px; right: 14px; }
.lb-prev { left: 14px; top: 50%; transform: translateY(-50%); }
.lb-next { right: 14px; top: 50%; transform: translateY(-50%); }

@media (max-width: 640px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
  .topbar { padding: 10px; }
  .title h1 { font-size: 16px; }
}
"""


JS = r"""
(() => {
  const M = window.MANIFEST || { entries: [], stats: {} };
  const entries = M.entries || [];

  const grid = document.getElementById('grid');
  const countLabel = document.getElementById('countLabel');
  const yearSel = document.getElementById('yearFilter');
  const monthSel = document.getElementById('monthFilter');
  const typeSel = document.getElementById('typeFilter');
  const sortSel = document.getElementById('sortFilter');
  const tabsEl = document.getElementById('tabs');

  // Build tabs from unique source values. Snapchat-ish labels are mapped, the
  // rest get Title Case. Hide the bar when there are fewer than 2 sources.
  const SOURCE_LABELS = { chat: 'Chat Media', memories: 'Memories' };
  const sourceLabel = (s) =>
    SOURCE_LABELS[s] || (s ? s[0].toUpperCase() + s.slice(1) : s);
  const sourcesInData = Array.from(
    new Set(entries.map((e) => e.source).filter(Boolean))
  ).sort();
  if (sourcesInData.length >= 2) {
    const defs = [{ value: 'all', label: 'All' }]
      .concat(sourcesInData.map((s) => ({ value: s, label: sourceLabel(s) })));
    for (let i = 0; i < defs.length; i++) {
      const btn = document.createElement('button');
      btn.className = 'tab' + (i === 0 ? ' active' : '');
      btn.dataset.source = defs[i].value;
      btn.textContent = defs[i].label;
      tabsEl.appendChild(btn);
    }
  }
  const tabs = Array.from(document.querySelectorAll('.tab'));

  const lightbox = document.getElementById('lightbox');
  const lbStage = lightbox.querySelector('.lb-stage');
  const lbMeta = lightbox.querySelector('.lb-meta');
  const lbClose = lightbox.querySelector('.lb-close');
  const lbPrev = lightbox.querySelector('.lb-prev');
  const lbNext = lightbox.querySelector('.lb-next');

  const state = {
    source: 'all',
    year: '',
    month: '',
    type: '',
    sort: 'desc',
    view: [],
    index: -1,
  };

  const years = Array.from(new Set(entries.map((e) => e.date.slice(0, 4))))
    .sort()
    .reverse();
  for (const y of years) {
    const opt = document.createElement('option');
    opt.value = y; opt.textContent = y;
    yearSel.appendChild(opt);
  }

  function applyFilters() {
    let v = entries.filter((e) => {
      if (state.source !== 'all' && e.source !== state.source) return false;
      if (state.year && e.date.slice(0, 4) !== state.year) return false;
      if (state.month && e.date.slice(5, 7) !== state.month) return false;
      if (state.type && e.type !== state.type) return false;
      return true;
    });
    v.sort((a, b) => state.sort === 'desc' ? b.mtime - a.mtime : a.mtime - b.mtime);
    state.view = v;
    render();
  }

  function fmtSize(n) {
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(0) + ' KB';
    return (n / 1024 / 1024).toFixed(1) + ' MB';
  }

  function render() {
    countLabel.textContent = state.view.length + ' of ' + entries.length + ' items';
    grid.innerHTML = '';
    if (state.view.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = 'No items match the current filters.';
      grid.appendChild(empty);
      return;
    }
    // Render in batches to keep first paint snappy on very large galleries.
    const BATCH = 300;
    let i = 0;
    function chunk() {
      const frag = document.createDocumentFragment();
      const end = Math.min(i + BATCH, state.view.length);
      for (; i < end; i++) frag.appendChild(buildTile(state.view[i], i));
      grid.appendChild(frag);
      if (i < state.view.length) requestAnimationFrame(chunk);
    }
    chunk();
  }

  // Lazily mount/unmount <video> elements for tiles without a thumbnail so we
  // stay under Chrome's WebMediaPlayer cap (~75). Only visible tiles hold one.
  const videoObserver = new IntersectionObserver((observed) => {
    for (const row of observed) {
      const tile = row.target;
      if (row.isIntersecting) {
        if (tile.querySelector('video')) continue;
        const v = document.createElement('video');
        v.src = tile.dataset.lazyVideo;
        v.preload = 'metadata';
        v.muted = true;
        v.playsInline = true;
        tile.insertBefore(v, tile.firstChild);
      } else {
        const v = tile.querySelector('video');
        if (v) {
          v.removeAttribute('src');
          v.load();
          v.remove();
        }
      }
    }
  }, { rootMargin: '200px' });

  function buildTile(e, idx) {
    const tile = document.createElement('div');
    tile.className = 'tile';
    tile.dataset.idx = idx;

    if (e.type === 'video') {
      if (e.thumb) {
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.src = e.thumb;
        tile.appendChild(img);
      } else {
        tile.dataset.lazyVideo = e.media;
        videoObserver.observe(tile);
      }
      const badge = document.createElement('span');
      badge.className = 'badge play';
      badge.textContent = 'Video';
      tile.appendChild(badge);
    } else {
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.src = e.media;
      tile.appendChild(img);
    }
    if (e.overlay) {
      const ov = document.createElement('img');
      ov.className = 'tile-overlay';
      ov.loading = 'lazy';
      ov.src = e.overlay;
      tile.appendChild(ov);
    }

    if (e.source) {
      const src = document.createElement('span');
      src.className = 'badge';
      src.textContent = sourceLabel(e.source);
      tile.appendChild(src);
    }

    const date = document.createElement('span');
    date.className = 'date';
    date.textContent = e.date;
    tile.appendChild(date);

    tile.addEventListener('click', () => openLightbox(idx));
    return tile;
  }

  function openLightbox(idx) {
    state.index = idx;
    showCurrent();
    lightbox.hidden = false;
    document.body.style.overflow = 'hidden';
  }
  function closeLightbox() {
    lightbox.hidden = true;
    lbStage.innerHTML = '';
    document.body.style.overflow = '';
  }
  function step(delta) {
    if (state.view.length === 0) return;
    state.index = (state.index + delta + state.view.length) % state.view.length;
    showCurrent();
  }
  function showCurrent() {
    const e = state.view[state.index];
    if (!e) return;
    lbStage.innerHTML = '';
    if (e.type === 'video') {
      const v = document.createElement('video');
      v.src = e.media;
      v.controls = true;
      v.autoplay = true;
      v.playsInline = true;
      if (e.thumb) v.poster = e.thumb;
      lbStage.appendChild(v);
    } else {
      const img = document.createElement('img');
      img.src = e.media;
      img.alt = e.name;
      lbStage.appendChild(img);
    }
    if (e.overlay) {
      const ov = document.createElement('img');
      ov.className = 'lb-overlay';
      ov.src = e.overlay;
      lbStage.appendChild(ov);
    }

    const parts = [
      e.exact_time || e.date,
      e.source ? sourceLabel(e.source) : null,
      e.folder,
      e.type,
      fmtSize(e.size),
    ].filter(Boolean);
    if (e.sender) parts.push('from ' + e.sender);
    if (e.conversation) parts.push('in ' + e.conversation);
    if (e.location) parts.push(e.location);
    lbMeta.innerHTML = '<strong>' + (state.index + 1) + ' / ' + state.view.length + '</strong>'
      + '<span class="muted">' + parts.join(' \u00b7 ') + '</span>';
  }

  tabs.forEach((t) => t.addEventListener('click', () => {
    tabs.forEach((x) => x.classList.remove('active'));
    t.classList.add('active');
    state.source = t.dataset.source;
    applyFilters();
  }));
  yearSel.addEventListener('change', () => { state.year = yearSel.value; applyFilters(); });
  monthSel.addEventListener('change', () => { state.month = monthSel.value; applyFilters(); });
  typeSel.addEventListener('change', () => { state.type = typeSel.value; applyFilters(); });
  sortSel.addEventListener('change', () => { state.sort = sortSel.value; applyFilters(); });

  lbClose.addEventListener('click', closeLightbox);
  lbPrev.addEventListener('click', () => step(-1));
  lbNext.addEventListener('click', () => step(1));
  lightbox.addEventListener('click', (ev) => {
    if (ev.target === lightbox) closeLightbox();
  });
  document.addEventListener('keydown', (ev) => {
    if (lightbox.hidden) return;
    if (ev.key === 'Escape') closeLightbox();
    else if (ev.key === 'ArrowLeft') step(-1);
    else if (ev.key === 'ArrowRight') step(1);
  });

  applyFilters();
})();
"""
