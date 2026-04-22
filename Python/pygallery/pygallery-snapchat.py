#!/usr/bin/env python3
"""Generate a static HTML gallery from Snapchat data export folders.

Scans every ``mydata~*/chat_media/`` and ``mydata~*/memories/`` folder under
the chosen root (defaults to the script's own directory), groups related
Snapchat files (media + thumbnail + overlay) that share a timestamp, and
emits a self-contained ``gallery.html`` plus assets in ``gallery/`` via the
shared :mod:`_core` module. Stdlib only.

Usage:
    python pygallery-snapchat.py                        # scan script directory
    python pygallery-snapchat.py D:\\Temp\\Snapchat     # scan given directory
    python pygallery-snapchat.py --enrich               # join chat_history.json etc.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _core import (
    FileInfo,
    KIND_MEDIA,
    KIND_METADATA,
    KIND_OTHER,
    KIND_OVERLAY,
    KIND_STANDALONE,
    KIND_THUMB,
    build_stats,
    make_entry,
    parse_date,
    print_summary,
    rel_url,
    write_outputs,
)


DEFAULT_ROOT = Path(__file__).resolve().parent
TITLE = "Snapchat Gallery"

MEMORY_SUFFIX_RE = re.compile(r"^(.+?)-(main|overlay)$")
MEMORY_MID_RE = re.compile(r"mid=([0-9a-fA-F-]+)")


# -----------------------------------------------------------------------------
# Filename classification and grouping (Snapchat-specific)
# -----------------------------------------------------------------------------


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


def group_key(f: FileInfo) -> tuple | None:
    """Group key that links Snapchat file components into one snap.

    - Chat media: sibling files share date and mtime down to the second.
    - Memories: sibling ``-main`` and ``-overlay`` files share a UUID stem.
    - Standalone ``b~`` files and anything else: ``None`` (each stays separate).
    """
    if f.source == "chat" and f.kind in (KIND_MEDIA, KIND_THUMB, KIND_OVERLAY):
        return (f.folder, f.date, f.mtime)
    if f.source == "memories" and f.kind in (KIND_MEDIA, KIND_OVERLAY):
        m = MEMORY_SUFFIX_RE.match(f.path.stem)
        if m:
            return (f.folder, m.group(1))
    return None


# -----------------------------------------------------------------------------
# Scanning
# -----------------------------------------------------------------------------


def scan_folder(folder: Path, source: str, root: Path) -> list[FileInfo]:
    """Return classified ``FileInfo`` entries from ``folder`` (non-recursive)."""
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
            rel=rel_url(p, root),
            date=date,
            mtime=mtime,
            size=st.st_size,
            ext=p.suffix.lower(),
            kind=kind,
            folder=folder_name,
            source=source,
        ))
    return out


def collect_files(root: Path) -> list[FileInfo]:
    files: list[FileInfo] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("mydata~")):
        for sub, source in (("chat_media", "chat"), ("memories", "memories")):
            sub_path = d / sub
            if sub_path.is_dir():
                files.extend(scan_folder(sub_path, source, root))
    return files


# -----------------------------------------------------------------------------
# Grouping and entry building
# -----------------------------------------------------------------------------


def _entries_from_group(parts: list[FileInfo], stats: dict) -> list[dict]:
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
            entry = make_entry(
                thumb_list[0],
                overlay=overlay_list[0] if len(overlay_list) == 1 else None,
            )
            return [entry] if entry else []
        stats["skipped_no_media"] = stats.get("skipped_no_media", 0) + 1
        return []

    def pick(i: int, pool: list[FileInfo]) -> FileInfo | None:
        if len(pool) == len(media_list):
            return pool[i]
        if len(pool) == 1:
            return pool[0]
        return None

    out: list[dict] = []
    for i, media in enumerate(media_list):
        entry = make_entry(media, thumb=pick(i, thumb_list), overlay=pick(i, overlay_list))
        if entry:
            out.append(entry)
    return out


def build_entries(files: list[FileInfo]) -> tuple[list[dict], dict]:
    entries: list[dict] = []
    extras = {"skipped_no_media": 0, "other_files": 0}

    groups: dict[tuple, list[FileInfo]] = {}
    for f in files:
        key = group_key(f)
        if key is not None:
            groups.setdefault(key, []).append(f)
        elif f.kind == KIND_STANDALONE:
            e = make_entry(f)
            if e:
                entries.append(e)
        else:
            extras["other_files"] += 1

    for parts in groups.values():
        entries.extend(_entries_from_group(parts, extras))

    entries.sort(key=lambda e: e["mtime"], reverse=True)
    stats = build_stats(entries, total_files=len(files), **extras)
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


def _index_entries_for_enrich(entries: list[dict]) -> dict[str, dict]:
    """Index entries by the UUID shapes found in Snapchat's JSON history.

    Snapchat's JSON references media via ``b~<hash>`` (chats) or a raw UUID
    embedded as ``mid=<uuid>`` (memories). We index both shapes so downstream
    lookups succeed regardless of which one the JSON gives us.
    """
    index: dict[str, dict] = {}
    for e in entries:
        _, after = parse_date(Path(e["name"]).stem, e["mtime"])
        index.setdefault(after, e)
        mm = MEMORY_SUFFIX_RE.match(after)
        if mm:
            index.setdefault(mm.group(1), e)
    return index


def enrich_entries(entries: list[dict], root: Path) -> int:
    """Join entries with ``chat_history.json`` and ``memories_history.json``.

    Adds ``sender``, ``exact_time``, ``conversation``, and ``location`` fields
    to any entry that matches by Media ID.
    """
    index = _index_entries_for_enrich(entries)
    matched = 0
    for d in root.iterdir():
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
# Entry point
# -----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("root", nargs="?", default=None,
                        help="Directory containing mydata~* folders "
                             "(default: this script's directory).")
    parser.add_argument("--enrich", action="store_true",
                        help="Join with chat_history.json / memories_history.json")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else DEFAULT_ROOT
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1

    files = collect_files(root)
    if not files:
        print(f"No Snapchat media files found in {root}.", file=sys.stderr)
        print(f"Expected directories: {root}/mydata~*/chat_media", file=sys.stderr)
        return 1

    entries, stats = build_entries(files)

    extras_summary: dict = {}
    if args.enrich:
        extras_summary["Enriched from JSON"] = enrich_entries(entries, root)
    if stats.get("skipped_no_media"):
        extras_summary["Groups without media"] = stats["skipped_no_media"]
    if stats.get("other_files"):
        extras_summary["Unclassified files"] = stats["other_files"]

    out_html = write_outputs(entries, stats, root=root, title=TITLE)
    print_summary(entries, stats, title=TITLE, out_html=out_html, extras=extras_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
