#!/usr/bin/env python3
"""Generate a static HTML gallery from Snapchat data export folders.

Scans every ``mydata~*/chat_media/`` and ``mydata~*/memories/`` folder next to
this script, groups related Snapchat files (media + thumbnail + overlay) that
share a timestamp, and emits a single self-contained ``gallery.html`` together
with ``gallery/style.css`` and ``gallery/app.js``. Stdlib only.

Usage:
    python generate_gallery.py            # generate the gallery
    python generate_gallery.py --enrich   # also join chat_history.json etc.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT_HTML = ROOT / "gallery.html"
OUT_DIR = ROOT / "gallery"
OUT_CSS = OUT_DIR / "style.css"
OUT_JS = OUT_DIR / "app.js"
OUT_MANIFEST = OUT_DIR / "manifest.json"

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)$")
MEMORY_SUFFIX_RE = re.compile(r"^(.+?)-(main|overlay)$")
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".m4v"}

# Classification tags used across the pipeline.
KIND_MEDIA = "media"
KIND_THUMB = "thumbnail"
KIND_OVERLAY = "overlay"
KIND_METADATA = "metadata"
KIND_STANDALONE = "standalone"
KIND_OTHER = "other"


# -----------------------------------------------------------------------------
# Data types
# -----------------------------------------------------------------------------


@dataclass
class FileInfo:
    path: Path
    rel: str           # URL-encoded path relative to gallery.html
    date: str          # YYYY-MM-DD
    mtime: int         # seconds since epoch
    size: int
    ext: str           # lowercase including leading dot
    kind: str
    folder: str        # mydata~... root name
    source: str        # "chat" | "memories"


# -----------------------------------------------------------------------------
# Filename parsing and classification
# -----------------------------------------------------------------------------


def rel_url(p: Path) -> str:
    """URL-safe path relative to the gallery root (forward slashes, % encoded)."""
    rel = p.relative_to(ROOT).as_posix()
    return "/".join(urllib.parse.quote(seg) for seg in rel.split("/"))


def parse_date(name_stem: str, mtime: int) -> tuple[str, str]:
    """Return (date, stem_after_date). Falls back to mtime when no prefix."""
    m = DATE_RE.match(name_stem)
    if m:
        return m.group(1), m.group(2)
    fallback = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    return fallback, name_stem


def classify(after_date: str, source: str) -> str:
    if after_date.startswith("media~"):
        return KIND_MEDIA
    if after_date.startswith("thumbnail~"):
        return KIND_THUMB
    if after_date.startswith("overlay~"):
        return KIND_OVERLAY
    if after_date.startswith("metadata~"):
        return KIND_METADATA
    if after_date.startswith("b~"):
        return KIND_STANDALONE
    if source == "memories":
        if after_date.endswith("-main"):
            return KIND_MEDIA
        if after_date.endswith("-overlay"):
            return KIND_OVERLAY
    return KIND_OTHER


def group_key(f: "FileInfo") -> tuple | None:
    """Group key that links Snapchat file components into one snap.

    - Chat media: sibling files share date and mtime down to the second.
    - Memories: sibling ``-main`` and ``-overlay`` files share a UUID stem.
    - Standalone b~ files and anything else: ``None`` (each stays separate).
    """
    if f.source == "chat" and f.kind in (KIND_MEDIA, KIND_THUMB, KIND_OVERLAY):
        return (f.folder, f.date, f.mtime)
    if f.source == "memories" and f.kind in (KIND_MEDIA, KIND_OVERLAY):
        m = MEMORY_SUFFIX_RE.match(f.path.stem)
        if m:
            return (f.folder, m.group(1))
    return None


def media_type(ext: str) -> str | None:
    if ext in IMG_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


# -----------------------------------------------------------------------------
# Scanning
# -----------------------------------------------------------------------------


def scan_folder(folder: Path, source: str) -> list[FileInfo]:
    folder_name = folder.parent.name
    out: list[FileInfo] = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        mtime = int(st.st_mtime)
        date, after = parse_date(p.stem, mtime)
        kind = classify(after, source)
        if kind == KIND_METADATA:
            continue
        out.append(FileInfo(
            path=p,
            rel=rel_url(p),
            date=date,
            mtime=mtime,
            size=st.st_size,
            ext=p.suffix.lower(),
            kind=kind,
            folder=folder_name,
            source=source,
        ))
    return out


def collect_files() -> list[FileInfo]:
    files: list[FileInfo] = []
    for d in sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("mydata~")):
        for sub, source in (("chat_media", "chat"), ("memories", "memories")):
            sub_path = d / sub
            if sub_path.is_dir():
                files.extend(scan_folder(sub_path, source))
    return files


# -----------------------------------------------------------------------------
# Grouping
# -----------------------------------------------------------------------------


def _entries_from_group(parts: list["FileInfo"], stats: dict) -> list[dict]:
    """Emit one entry per media file in a group.

    When the group contains N media and N overlays (or N thumbs), pair them
    by sorted filename position so each media gets its own sibling. When counts
    differ, fall back to attaching the single sibling if there's exactly one,
    otherwise drop the sibling for that entry (avoids wrong composites).
    """
    media_list = sorted((f for f in parts if f.kind == KIND_MEDIA), key=lambda f: f.path.name)
    thumb_list = sorted((f for f in parts if f.kind == KIND_THUMB), key=lambda f: f.path.name)
    overlay_list = sorted((f for f in parts if f.kind == KIND_OVERLAY), key=lambda f: f.path.name)

    if not media_list:
        if thumb_list:
            return [e for e in (_make_entry(thumb_list[0], overlay=overlay_list[0] if len(overlay_list) == 1 else None),) if e]
        stats["skipped_no_media"] += 1
        return []

    def _pick(i: int, pool: list["FileInfo"]) -> "FileInfo | None":
        if len(pool) == len(media_list):
            return pool[i]
        if len(pool) == 1:
            return pool[0]
        return None

    out: list[dict] = []
    for i, media in enumerate(media_list):
        e = _make_entry(
            media,
            thumb=_pick(i, thumb_list),
            overlay=_pick(i, overlay_list),
        )
        if e:
            out.append(e)
    return out


def _make_entry(primary: FileInfo, *, thumb: FileInfo | None = None,
                overlay: FileInfo | None = None) -> dict:
    mtype = media_type(primary.ext)
    if mtype is None:
        return {}
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


def build_entries(files: list[FileInfo]) -> tuple[list[dict], dict]:
    entries: list[dict] = []
    stats: dict = {
        "total_files": len(files),
        "skipped_no_media": 0,
        "other_files": 0,
        "by_year": {},
        "by_source": {"chat": 0, "memories": 0},
        "by_type": {"image": 0, "video": 0},
    }

    groups: dict[tuple, list[FileInfo]] = {}
    for f in files:
        key = group_key(f)
        if key is not None:
            groups.setdefault(key, []).append(f)
        elif f.kind == KIND_STANDALONE:
            e = _make_entry(f)
            if e:
                entries.append(e)
        else:
            stats["other_files"] += 1

    for parts in groups.values():
        entries.extend(_entries_from_group(parts, stats))

    entries.sort(key=lambda e: e["mtime"], reverse=True)

    for e in entries:
        stats["by_year"][e["date"][:4]] = stats["by_year"].get(e["date"][:4], 0) + 1
        stats["by_source"][e["source"]] += 1
        stats["by_type"][e["type"]] += 1

    return entries, stats


# -----------------------------------------------------------------------------
# Optional enrichment from Snapchat JSON history
# -----------------------------------------------------------------------------


def _load_json_maybe(p: Path) -> object | None:
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


MEMORY_MID_RE = re.compile(r"mid=([0-9a-fA-F-]+)")


def _index_entries_for_enrich(entries: list[dict]) -> dict[str, dict]:
    """Index entries by several lookup keys.

    Snapchat filenames carry a UUID that uniquely identifies the piece of
    media. We index by a few shapes of that UUID so downstream lookups can
    succeed whether the JSON gives us ``b~<hash>`` or a raw UUID.
    """
    index: dict[str, dict] = {}
    for e in entries:
        stem = Path(e["name"]).stem
        m = DATE_RE.match(stem)
        after = m.group(2) if m else stem
        # For chat b~ files: `Media IDs` in chat_history.json contains the full
        # "b~<hash>" string, which equals `after` directly.
        index.setdefault(after, e)
        # For memories: the filename carries the UUID as its stem, plus suffix.
        mm = MEMORY_SUFFIX_RE.match(after)
        if mm:
            index.setdefault(mm.group(1), e)
    return index


def enrich_entries(entries: list[dict]) -> int:
    """Join entries with ``chat_history.json`` and ``memories_history.json``.

    Adds ``sender``, ``exact_time``, ``conversation``, and ``location`` fields
    to any entry that matches by Media ID.
    """
    index = _index_entries_for_enrich(entries)
    matched = 0

    for d in ROOT.iterdir():
        if not (d.is_dir() and d.name.startswith("mydata~")):
            continue
        json_dir = d / "json"
        matched += _enrich_chat(index, _load_json_maybe(json_dir / "chat_history.json"))
        matched += _enrich_memories(index, _load_json_maybe(json_dir / "memories_history.json"))
    return matched


def _enrich_chat(index: dict[str, dict], data: object) -> int:
    if not isinstance(data, dict):
        return 0
    matched = 0
    for conv_key, msgs in data.items():
        if not isinstance(msgs, list):
            continue
        for msg in msgs:
            if not isinstance(msg, dict):
                continue
            mids = msg.get("Media IDs")
            if not mids or not isinstance(mids, str):
                continue
            sender = msg.get("From")
            created = msg.get("Created")
            conv_title = msg.get("Conversation Title") or conv_key
            for mid in (s.strip() for s in mids.split(",")):
                entry = index.get(mid)
                if entry is None:
                    continue
                if sender:
                    entry.setdefault("sender", sender)
                if created:
                    entry.setdefault("exact_time", created)
                if conv_title:
                    entry.setdefault("conversation", conv_title)
                matched += 1
    return matched


def _enrich_memories(index: dict[str, dict], data: object) -> int:
    if not isinstance(data, dict):
        return 0
    saved = data.get("Saved Media")
    if not isinstance(saved, list):
        return 0
    matched = 0
    for item in saved:
        if not isinstance(item, dict):
            continue
        link = item.get("Download Link") or item.get("Media Download Url") or ""
        m = MEMORY_MID_RE.search(link) if isinstance(link, str) else None
        if not m:
            continue
        entry = index.get(m.group(1))
        if entry is None:
            continue
        date = item.get("Date")
        loc = item.get("Location")
        if date:
            entry.setdefault("exact_time", date)
        if loc:
            entry.setdefault("location", loc)
        matched += 1
    return matched


# -----------------------------------------------------------------------------
# Output (HTML / CSS / JS templates)
# -----------------------------------------------------------------------------


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Snapchat Gallery</title>
<link rel="stylesheet" href="gallery/style.css">
</head>
<body>
<header class="topbar">
  <div class="title">
    <h1>Snapchat Gallery</h1>
    <span id="countLabel" class="muted"></span>
  </div>
  <nav class="tabs" role="tablist">
    <button class="tab active" data-source="all">All</button>
    <button class="tab" data-source="chat">Chat Media</button>
    <button class="tab" data-source="memories">Memories</button>
  </nav>
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
  --accent: #fffc00;   /* Snapchat yellow */
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

  // --- Populate year filter from data ---
  const years = Array.from(new Set(entries.map(e => e.date.slice(0, 4)))).sort().reverse();
  for (const y of years) {
    const opt = document.createElement('option');
    opt.value = y; opt.textContent = y;
    yearSel.appendChild(opt);
  }

  // --- Filtering ---
  function applyFilters() {
    let v = entries.filter(e => {
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

  // Lazily mount/unmount <video> elements for tiles without a thumbnail to
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
        // Snapchat exports often lack a thumbnail for videos. We can't spawn
        // hundreds of <video> elements (Chrome caps live WebMediaPlayers), so
        // the <video> is created lazily when the tile scrolls into view and
        // torn down when it leaves.
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

    const src = document.createElement('span');
    src.className = 'badge';
    src.textContent = e.source === 'memories' ? 'Memory' : 'Chat';
    tile.appendChild(src);

    const date = document.createElement('span');
    date.className = 'date';
    date.textContent = e.date;
    tile.appendChild(date);

    tile.addEventListener('click', () => openLightbox(idx));
    return tile;
  }

  // --- Lightbox ---
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
      e.source === 'memories' ? 'Memory' : 'Chat',
      e.type,
      fmtSize(e.size),
    ];
    if (e.sender) parts.push('from ' + e.sender);
    if (e.conversation) parts.push('in ' + e.conversation);
    if (e.location) parts.push(e.location);
    lbMeta.innerHTML = '<strong>' + (state.index + 1) + ' / ' + state.view.length + '</strong>'
      + '<span class="muted">' + parts.join(' \u00b7 ') + '</span>';
  }

  // --- Wire up UI ---
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
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


# -----------------------------------------------------------------------------
# Writing output
# -----------------------------------------------------------------------------


def write_outputs(entries: list[dict], stats: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)

    manifest = {"entries": entries, "stats": stats, "generated_at": datetime.now().isoformat(timespec="seconds")}
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Inline the manifest so the HTML works when opened via file:// (no fetch).
    inlined = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    OUT_HTML.write_text(
        HTML_TEMPLATE.replace("__MANIFEST__", inlined),
        encoding="utf-8",
    )
    OUT_CSS.write_text(CSS, encoding="utf-8")
    OUT_JS.write_text(JS, encoding="utf-8")


def print_summary(entries: list[dict], stats: dict, enriched: int | None) -> None:
    print(f"Gallery generated: {len(entries)} items")
    print(f"  Source files scanned:  {stats['total_files']}")
    print(f"  Chat Media:            {stats['by_source']['chat']}")
    print(f"  Memories:              {stats['by_source']['memories']}")
    print(f"  Photos:                {stats['by_type']['image']}")
    print(f"  Videos:                {stats['by_type']['video']}")
    if stats["skipped_no_media"]:
        print(f"  Groups without media:  {stats['skipped_no_media']}")
    if stats["other_files"]:
        print(f"  Unclassified files:    {stats['other_files']}")
    if enriched is not None:
        print(f"  Enriched from JSON:    {enriched}")
    if stats["by_year"]:
        print("  By year:")
        for year in sorted(stats["by_year"].keys()):
            print(f"    {year}: {stats['by_year'][year]}")
    print(f"\nOpen: {OUT_HTML}")


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrich", action="store_true",
                        help="Join with chat_history.json / memories_history.json")
    args = parser.parse_args(argv)

    files = collect_files()
    if not files:
        print("No media files found next to this script.", file=sys.stderr)
        print(f"Expected directories: {ROOT}/mydata~*/chat_media", file=sys.stderr)
        return 1

    entries, stats = build_entries(files)
    enriched: int | None = None
    if args.enrich:
        enriched = enrich_entries(entries)

    write_outputs(entries, stats)
    print_summary(entries, stats, enriched)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
