#!/usr/bin/env python3
"""Build a local HTML media gallery (videos + images) grouped by folder, with thumbnails.

Usage:
  python3 build_gallery.py --help
  python3 build_gallery.py
  python3 build_gallery.py /path/to/media/library
  python3 build_gallery.py /path/to/media/library -o /path/to/output/_gallery

Missing options are prompted interactively.

Requires: ffmpegthumbnailer (preferred for videos) or ffmpeg.
For reliable video seeking in the browser, serve the library root over HTTP with Range support.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# Set in main() from CLI args
LIBRARY: Path
GALLERY: Path
THUMBS: Path
INDEX: Path

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
MEDIA_EXTS = VIDEO_EXTS | IMAGE_EXTS
SKIP_DIRS = {"_gallery", "_inbox"}
THUMB_SIZE = 480
WORKERS = 6


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def rel_posix(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path.resolve(), start.resolve())).as_posix()


def rel_url(path: Path, start: Path) -> str:
    """Relative path safe for use in href/src (encodes +, spaces, etc.)."""
    parts = rel_posix(path, start).split("/")
    return "/".join(
        part if part in (".", "..") else quote(part, safe="")
        for part in parts
    )


def thumb_path_for(media: Path) -> Path:
    digest = hashlib.sha1(str(media.resolve()).encode()).hexdigest()[:16]
    return THUMBS / f"{digest}.jpg"


def list_media() -> list[tuple[str, Path]]:
    """Return (folder_label, media_path) sorted by folder then name."""
    items: list[tuple[str, Path]] = []
    for path in LIBRARY.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in MEDIA_EXTS:
            continue
        try:
            rel = path.relative_to(LIBRARY)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        folder = rel.parts[0] if len(rel.parts) > 1 else "_root"
        items.append((folder, path))
    items.sort(key=lambda t: (t[0].casefold(), t[1].name.casefold()))
    return items


def make_thumb(media: Path, thumb: Path) -> tuple[Path, str]:
    if thumb.exists() and thumb.stat().st_mtime >= media.stat().st_mtime:
        return media, "cached"
    thumb.parent.mkdir(parents=True, exist_ok=True)
    tmp = thumb.with_suffix(".tmp.jpg")

    if is_image(media):
        # Resize stills; fall back to copying the original via ffmpeg if needed.
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(media),
                    "-vf",
                    f"scale='min({THUMB_SIZE},iw)':-1",
                    "-frames:v",
                    "1",
                    "-q:v",
                    "4",
                    str(tmp),
                ],
                check=True,
                capture_output=True,
            )
            tmp.replace(thumb)
            return media, "ok"
        except Exception as e:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            return media, f"fail:{e}"

    try:
        subprocess.run(
            [
                "ffmpegthumbnailer",
                "-i",
                str(media),
                "-o",
                str(tmp),
                "-s",
                str(THUMB_SIZE),
                "-q",
                "6",
                "-f",
            ],
            check=True,
            capture_output=True,
        )
        tmp.replace(thumb)
        return media, "ok"
    except Exception as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    "5",
                    "-i",
                    str(media),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "4",
                    str(tmp),
                ],
                check=True,
                capture_output=True,
            )
            tmp.replace(thumb)
            return media, "ffmpeg"
        except Exception:
            return media, f"fail:{e}"


def format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def format_date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def build_html(items: list[tuple[str, Path, Path | None, int, float]]) -> str:
    """items: folder, media, thumb_or_None, size, mtime"""
    groups: dict[str, list[tuple[Path, Path | None, int, float]]] = {}
    for folder, media, thumb, size, mtime in items:
        groups.setdefault(folder, []).append((media, thumb, size, mtime))

    video_count = sum(1 for _, media, *_ in items if is_video(media))
    image_count = sum(1 for _, media, *_ in items if is_image(media))

    folder_links = []
    sections = []
    for folder in sorted(groups, key=str.casefold):
        media_items = groups[folder]
        newest = max(m for *_, m in media_items)
        total_size = sum(s for _, _, s, _ in media_items)
        anchor = hashlib.sha1(folder.encode()).hexdigest()[:10]
        folder_links.append(
            f'<a href="#{html.escape(anchor)}" data-folder="{html.escape(folder)}" '
            f'data-name="{html.escape(folder.casefold())}" data-date="{newest:.0f}" data-size="{total_size}">'
            f"{html.escape(folder)} <span>{len(media_items)}</span></a>"
        )
        cards = []
        for media, thumb, size, mtime in media_items:
            media_href = rel_url(media, GALLERY)
            title = media.stem
            kind = "image" if is_image(media) else "video"
            badge = "" if kind == "image" else '<span class="play">▶</span>'
            open_label = "Open image" if kind == "image" else "Open video"
            thumb_html = (
                f'<img src="{html.escape(rel_url(thumb, GALLERY))}" alt="" loading="lazy">'
                if thumb and thumb.exists()
                else '<div class="no-thumb">No preview</div>'
            )
            cards.append(
                f"""
<article class="card" data-name="{html.escape(title.casefold())}" data-folder="{html.escape(folder.casefold())}" data-date="{mtime:.0f}" data-size="{size}" data-kind="{kind}">
  <a class="thumb" href="{html.escape(media_href)}" target="_blank" rel="noopener" title="{open_label}">
    {thumb_html}
    {badge}
  </a>
  <div class="meta">
    <a class="title" href="{html.escape(media_href)}" target="_blank" rel="noopener" title="{html.escape(media.name)}">{html.escape(title)}</a>
    <div class="sub">{html.escape(format_size(size))} · {html.escape(format_date(mtime))} · {kind}</div>
  </div>
</article>"""
            )
        sections.append(
            f"""
<section class="group" id="{html.escape(anchor)}" data-folder="{html.escape(folder.casefold())}" data-name="{html.escape(folder.casefold())}" data-date="{newest:.0f}" data-size="{total_size}">
  <h2>{html.escape(folder)} <span class="count">{len(media_items)}</span></h2>
  <div class="grid">
    {''.join(cards)}
  </div>
</section>"""
        )

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = []
    if video_count:
        parts.append(f"{video_count} video{'s' if video_count != 1 else ''}")
    if image_count:
        parts.append(f"{image_count} image{'s' if image_count != 1 else ''}")
    if not parts:
        parts.append("0 items")
    stats = f"{' · '.join(parts)} · {len(groups)} folders · generated {html.escape(generated)}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Media Library</title>
<style>
  :root {{
    --bg: #0f1115;
    --panel: #181b22;
    --ink: #e8eaef;
    --muted: #9aa3b2;
    --line: #2a303b;
    --accent: #3dbea5;
    --accent-soft: #1a3330;
    --shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
    --radius: 14px;
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; color-scheme: dark; }}
  body {{
    margin: 0;
    font: 15px/1.45 "Segoe UI", "IBM Plex Sans", system-ui, sans-serif;
    color: var(--ink);
    background:
      radial-gradient(1100px 560px at 8% -12%, #1a2a2f 0%, transparent 55%),
      radial-gradient(900px 480px at 100% 0%, #241c28 0%, transparent 50%),
      var(--bg);
  }}
  header {{
    position: sticky; top: 0; z-index: 20;
    backdrop-filter: blur(12px);
    background: color-mix(in srgb, var(--bg) 78%, black);
    border-bottom: 1px solid var(--line);
    padding: 14px 20px 12px;
  }}
  .top {{
    display: flex; gap: 16px; flex-wrap: wrap; align-items: end;
    justify-content: space-between; max-width: 1400px; margin: 0 auto;
  }}
  h1 {{
    margin: 0; font-size: 1.35rem; letter-spacing: -0.02em;
  }}
  .stats {{ color: var(--muted); font-size: 0.92rem; margin-top: 2px; }}
  .controls {{
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  }}
  input[type="search"], select {{
    padding: 10px 14px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--panel);
    color: var(--ink);
    outline: none;
    font: inherit;
  }}
  input[type="search"] {{
    width: min(280px, 60vw);
  }}
  input[type="search"]:focus, select:focus {{
    border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft);
  }}
  select {{
    padding-right: 28px;
    cursor: pointer;
  }}
  label.control-label {{
    color: var(--muted); font-size: 0.82rem; margin-right: -4px;
  }}
  .nav {{
    max-width: 1400px; margin: 10px auto 0;
    display: flex; gap: 8px; flex-wrap: wrap; max-height: 92px; overflow: auto;
  }}
  .nav a {{
    text-decoration: none; color: var(--ink);
    background: var(--panel); border: 1px solid var(--line);
    border-radius: 999px; padding: 6px 10px; font-size: 0.85rem;
    white-space: nowrap;
  }}
  .nav a span {{
    color: var(--muted); margin-left: 4px;
  }}
  .nav a:hover {{ border-color: var(--accent); background: var(--accent-soft); }}
  main {{ max-width: 1400px; margin: 0 auto; padding: 18px 20px 60px; }}
  .group {{ margin-bottom: 34px; }}
  .group.hidden, .card.hidden {{ display: none; }}
  h2 {{
    margin: 0 0 12px; font-size: 1.15rem; letter-spacing: -0.01em;
    display: flex; align-items: baseline; gap: 8px;
  }}
  h2 .count {{
    color: var(--muted); font-weight: 500; font-size: 0.9rem;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 14px;
  }}
  .card {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow);
    transition: transform .15s ease, box-shadow .15s ease;
  }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 16px 34px rgba(0,0,0,.45); }}
  .thumb {{
    position: relative; display: block; aspect-ratio: 16/9;
    background: #0a0c10; overflow: hidden;
  }}
  .thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .no-thumb {{
    width: 100%; height: 100%; display: grid; place-items: center;
    color: var(--muted); font-size: 0.9rem;
  }}
  .play {{
    position: absolute; inset: auto 10px 10px auto;
    background: rgba(61,190,165,.95); color: #04140f;
    width: 34px; height: 34px; border-radius: 50%;
    display: grid; place-items: center; font-size: 12px;
    opacity: 0; transform: scale(.9); transition: .15s ease;
  }}
  .card:hover .play {{ opacity: 1; transform: scale(1); }}
  .meta {{ padding: 10px 12px 12px; }}
  .title {{
    color: var(--ink); text-decoration: none; font-weight: 600;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; min-height: 2.7em;
  }}
  .title:hover {{ color: var(--accent); }}
  .sub {{ color: var(--muted); font-size: 0.82rem; margin-top: 4px; }}
  footer {{
    max-width: 1400px; margin: 0 auto; padding: 0 20px 40px;
    color: var(--muted); font-size: 0.85rem;
  }}
</style>
</head>
<body>
<div id="file-origin-banner" hidden style="display:none;background:#5c2b2b;color:#ffe8e8;padding:10px 16px;text-align:center;font-size:0.92rem;">
  Playing via <code>file://</code> can freeze videos in Chrome/Brave.
  Serve the library folder over HTTP (with Range support) instead.
</div>
<header>
  <div class="top">
    <div>
      <h1>Media Library</h1>
      <div class="stats">{stats}</div>
    </div>
    <div class="controls">
      <input type="search" id="q" placeholder="Filter by title, folder, or kind…" autocomplete="off">
      <label class="control-label" for="sort-by">Sort</label>
      <select id="sort-by" aria-label="Sort by">
        <option value="name">Name</option>
        <option value="date">Date</option>
        <option value="size">Size</option>
      </select>
      <select id="sort-dir" aria-label="Sort direction">
        <option value="asc">Ascending</option>
        <option value="desc">Descending</option>
      </select>
    </div>
  </div>
  <nav class="nav" id="nav">
    {''.join(folder_links)}
  </nav>
</header>
<main id="main">
  {''.join(sections)}
</main>
<footer>
  Open media via a local HTTP server for reliable video seeking. Regenerate with <code>build_gallery.py</code>.
</footer>

<script>
const q = document.getElementById('q');
const sortBy = document.getElementById('sort-by');
const sortDir = document.getElementById('sort-dir');
const main = document.getElementById('main');
const nav = document.getElementById('nav');
const STORAGE_KEY = 'video-library-sort';

if (location.protocol === 'file:') {{
  const banner = document.getElementById('file-origin-banner');
  banner.hidden = false;
  banner.style.display = 'block';
}}

function cards() {{ return [...document.querySelectorAll('.card')]; }}
function groups() {{ return [...document.querySelectorAll('.group')]; }}

function applyFilter() {{
  const term = q.value.trim().toLowerCase();
  cards().forEach(card => {{
    const hay = card.dataset.name + ' ' + card.dataset.folder + ' ' + (card.dataset.kind || '');
    card.classList.toggle('hidden', term && !hay.includes(term));
  }});
  groups().forEach(group => {{
    const visible = [...group.querySelectorAll('.card')].some(c => !c.classList.contains('hidden'));
    group.classList.toggle('hidden', !visible);
  }});
}}

function cmp(a, b, key, dir) {{
  let av = a.dataset[key];
  let bv = b.dataset[key];
  if (key === 'date' || key === 'size') {{
    av = Number(av);
    bv = Number(bv);
  }} else {{
    av = (av || '').toString();
    bv = (bv || '').toString();
  }}
  let result = av < bv ? -1 : av > bv ? 1 : 0;
  return dir === 'desc' ? -result : result;
}}

function applySort() {{
  const key = sortBy.value;
  const dir = sortDir.value;

  groups().forEach(group => {{
    const grid = group.querySelector('.grid');
    const list = [...grid.querySelectorAll('.card')];
    list.sort((a, b) => cmp(a, b, key, dir));
    list.forEach(card => grid.appendChild(card));
  }});

  const groupList = groups();
  groupList.sort((a, b) => cmp(a, b, key === 'name' ? 'name' : key, dir));
  groupList.forEach(g => main.appendChild(g));

  const navLinks = [...nav.querySelectorAll('a')];
  navLinks.sort((a, b) => cmp(a, b, key === 'name' ? 'name' : key, dir));
  navLinks.forEach(a => nav.appendChild(a));

  localStorage.setItem(STORAGE_KEY, JSON.stringify({{ key, dir }}));
}}

q.addEventListener('input', applyFilter);
sortBy.addEventListener('change', applySort);
sortDir.addEventListener('change', applySort);

try {{
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
  if (saved.key) sortBy.value = saved.key;
  if (saved.dir === 'asc' || saved.dir === 'desc') sortDir.value = saved.dir;
}} catch (_) {{}}
applySort();
</script>
</body>
</html>
"""


def prompt_path(label: str, default: Path | None = None, *, must_exist: bool = False) -> Path:
    """Ask for a path on stdin; empty input keeps default when provided."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        try:
            raw = input(f"{label}{suffix}: ").strip()
        except EOFError:
            if default is not None:
                return default.resolve()
            print("\nCancelled: no path provided.", file=sys.stderr)
            raise SystemExit(2) from None
        if not raw:
            if default is None:
                print("Please enter a path.", file=sys.stderr)
                continue
            value = default
        else:
            value = Path(raw).expanduser()
        value = value.resolve()
        if must_exist and not value.is_dir():
            print(f"Not a directory: {value}", file=sys.stderr)
            continue
        return value


def prompt_int(label: str, default: int, *, minimum: int = 1) -> int:
    while True:
        try:
            raw = input(f"{label} [{default}]: ").strip()
        except EOFError:
            return default
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.", file=sys.stderr)
            continue
        if value < minimum:
            print(f"Please enter a number >= {minimum}.", file=sys.stderr)
            continue
        return value


def main(argv: list[str] | None = None) -> int:
    global LIBRARY, GALLERY, THUMBS, INDEX

    parser = argparse.ArgumentParser(
        prog="build_gallery.py",
        description="Build a local HTML media gallery (videos + images) grouped by folder, with thumbnails.",
        epilog=(
            "If library / output / workers are omitted, you will be prompted. "
            "Example: python3 build_gallery.py --help"
        ),
    )
    parser.add_argument(
        "library",
        nargs="?",
        type=Path,
        default=None,
        help="Root folder containing videos/images (usually one subfolder per group)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Gallery output directory (default: <library>/_gallery)",
    )
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=None,
        help=f"Parallel thumbnail workers (default: {WORKERS})",
    )
    args = parser.parse_args(argv)

    # Prompt for anything not provided on the command line
    if args.library is None:
        print("Media HTML gallery builder")
        print("Press Enter to accept a default shown in [brackets].\n")
        library = prompt_path("Media library folder", must_exist=True)
    else:
        library = args.library.expanduser().resolve()
        if not library.is_dir():
            print(f"Not a directory: {library}", file=sys.stderr)
            return 1

    default_output = library / "_gallery"
    if args.output is None:
        output = prompt_path("Gallery output folder", default_output)
    else:
        output = args.output.expanduser().resolve()

    if args.workers is None:
        workers = prompt_int("Thumbnail worker threads", WORKERS, minimum=1)
    else:
        workers = max(1, args.workers)

    LIBRARY = library
    GALLERY = output
    THUMBS = GALLERY / "thumbs"
    INDEX = GALLERY / "index.html"

    print(f"\nLibrary : {LIBRARY}")
    print(f"Output  : {GALLERY}")
    print(f"Workers : {workers}\n")

    THUMBS.mkdir(parents=True, exist_ok=True)
    listed = list_media()
    print(f"Found {len(listed)} media files in {LIBRARY}")

    thumb_map: dict[Path, Path] = {}
    status_counts = {"ok": 0, "cached": 0, "ffmpeg": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(make_thumb, media, thumb_path_for(media)): media
            for _, media in listed
        }
        done = 0
        total = len(futures)
        for fut in as_completed(futures):
            media, status = fut.result()
            done += 1
            if status.startswith("fail"):
                status_counts["fail"] += 1
                print(f"[{done}/{total}] FAIL {media.name}: {status}")
            else:
                status_counts[status if status in status_counts else "ok"] += 1
                thumb_map[media] = thumb_path_for(media)
                if done % 25 == 0 or done == total:
                    print(f"[{done}/{total}] thumbs… ({status})")

    items = []
    for folder, media in listed:
        thumb = thumb_map.get(media)
        if thumb and not thumb.exists():
            thumb = None
        st = media.stat()
        items.append((folder, media, thumb, st.st_size, st.st_mtime))

    INDEX.write_text(build_html(items), encoding="utf-8")
    print(f"Wrote {INDEX}")
    print(f"Thumbs: {status_counts}")
    print(f"Open: xdg-open {INDEX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
