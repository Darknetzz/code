#!/usr/bin/env python3
"""Generate a static HTML gallery from any directory tree of media files.

Recursively walks the chosen directory, picks up images and videos by
extension, optionally builds ffmpeg thumbnails, and emits a self-contained
``gallery.html`` plus supporting assets in a ``gallery/`` subfolder via the
shared :mod:`_core` module.

By default a Range-capable HTTP server is started afterward so you can open
the gallery from this machine or another on the LAN. Use ``--no-serve`` to
only write files (``file://`` still works).

Tabs are auto-built from the first-level subfolders of the scanned root, so
e.g.::

    D:\\Photos\\
      Vacation2024\\...
      Screenshots\\...
      CameraRoll\\...

gets three tabs. If there's only one top-level folder (or none), the tab bar
is hidden and you get just the search / year / month / type filters.

Usage:
    python pygallery.py                      # interactive; then serve
    python pygallery.py D:\\Photos           # build + serve
    python pygallery.py D:\\Photos --no-serve
    python pygallery.py D:\\Photos --bind 127.0.0.1 --port 8080
    python pygallery.py D:\\Photos --title "My Photos" -j 8
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from _core import (
    FileInfo,
    KIND_STANDALONE,
    KIND_THUMB,
    MEDIA_EXTS,
    build_stats,
    make_entry,
    make_file_info,
    print_summary,
    write_outputs,
)
from _prompt import prompt_int, prompt_path
from _serve import DEFAULT_BIND, DEFAULT_PORT, serve_directory
from _thumbs import (
    DEFAULT_WORKERS,
    ensure_durations,
    generate_thumbs,
    media_needing_thumbs,
    thumb_path_for,
)


# Directory names we never descend into. Contains the output folder plus a
# conservative set of common junk dirs so scanning a repo or system folder
# doesn't churn through tens of thousands of irrelevant files.
DEFAULT_SKIP_DIRS = {
    "gallery",         # our own output
    "_gallery",
    "_inbox",
    "__pycache__",
    "node_modules",
    ".git", ".hg", ".svn",
    ".idea", ".vscode",
    "System Volume Information", "$RECYCLE.BIN",
}


def scan_tree(root: Path, out_dir: Path,
              skip_dirs: set[str] | None = None) -> list[FileInfo]:
    """Recursively collect media files under ``root`` as :class:`FileInfo`.

    Skips the generated output directory, dot-directories, and a small set of
    well-known junk folders. Does not follow symlinks.
    """
    skip = set(DEFAULT_SKIP_DIRS if skip_dirs is None else skip_dirs)
    skip.add(out_dir.name)

    files: list[FileInfo] = []
    for dirpath_str, dirnames, filenames in os.walk(root, followlinks=False):
        dirpath = Path(dirpath_str)

        # Prune so we don't descend into noisy / irrelevant subtrees.
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in skip
        ]
        if dirpath == out_dir or _is_relative_to(dirpath, out_dir):
            dirnames.clear()
            continue

        rel_parts = dirpath.relative_to(root).parts
        source = rel_parts[0] if rel_parts else ""
        folder = dirpath.name or root.name

        for fname in filenames:
            p = dirpath / fname
            if p.suffix.lower() not in MEDIA_EXTS:
                continue
            fi = make_file_info(p, root, kind=KIND_STANDALONE,
                                folder=folder, source=source)
            if fi is not None:
                files.append(fi)
    return files


def _is_relative_to(path: Path, other: Path) -> bool:
    """``Path.is_relative_to`` exists on 3.9+; keep a compat shim just in case."""
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=None,
        help="Directory to scan recursively. Prompted if omitted.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Asset output directory (default: <root>/gallery). Prompted if omitted.",
    )
    parser.add_argument(
        "-j", "--workers",
        type=int,
        default=None,
        help=f"Parallel thumbnail workers (default: {DEFAULT_WORKERS}). "
             "Prompted if omitted.",
    )
    parser.add_argument(
        "--no-thumbs",
        action="store_true",
        help="Skip ffmpeg/ffmpegthumbnailer thumbnail generation.",
    )
    parser.add_argument(
        "--no-serve",
        action="store_true",
        help="Only write gallery files; do not start the HTTP server.",
    )
    parser.add_argument(
        "--bind",
        default=DEFAULT_BIND,
        help=f"HTTP bind address (default: {DEFAULT_BIND}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"HTTP port (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--title",
        default="Media Gallery",
        help="Page title shown in the header (default: 'Media Gallery').",
    )
    args = parser.parse_args(argv)

    interactive = args.root is None
    if interactive:
        print("Media HTML gallery builder")
        print("Press Enter to accept a default shown in [brackets].\n")
        root = prompt_path("Media library folder", Path.cwd(), must_exist=True)
    else:
        root = args.root.expanduser().resolve()
        if not root.is_dir():
            print(f"Not a directory: {root}", file=sys.stderr)
            return 1

    default_output = root / "gallery"
    default_thumbs = default_output / "thumbs"
    if args.output is None:
        # Reuse existing gallery/thumbs without prompting when present.
        if default_thumbs.is_dir():
            out_dir = default_output
            print(f"Using existing thumbnails at {default_thumbs}")
        elif sys.stdin.isatty():
            out_dir = prompt_path("Gallery output folder", default_output)
        else:
            out_dir = default_output
    else:
        out_dir = args.output.expanduser().resolve()

    print(f"\nLibrary : {root}")
    print(f"Output  : {out_dir}")

    files = scan_tree(root, out_dir)
    if not files:
        print(f"No media files found in {root}", file=sys.stderr)
        print(f"Looking for extensions: {', '.join(sorted(MEDIA_EXTS))}",
              file=sys.stderr)
        return 1

    thumbs_dir = out_dir / "thumbs"
    pending_thumbs: list[Path] = []
    if not args.no_thumbs:
        pending_thumbs = media_needing_thumbs([f.path for f in files], thumbs_dir)

    if args.workers is None:
        if args.no_thumbs or not pending_thumbs:
            workers = DEFAULT_WORKERS
            if not args.no_thumbs and not pending_thumbs:
                print(
                    f"Thumbnails up to date "
                    f"({len(files)} cached in {thumbs_dir})"
                )
        elif sys.stdin.isatty():
            print(
                f"{len(pending_thumbs)} of {len(files)} media "
                f"need new/updated thumbnails"
            )
            workers = prompt_int(
                "Thumbnail worker threads", DEFAULT_WORKERS, minimum=1,
            )
        else:
            workers = DEFAULT_WORKERS
    else:
        workers = max(1, args.workers)

    if not args.no_thumbs:
        print(f"Workers : {workers}")
    print()

    thumb_map: dict[Path, Path] = {}
    status_counts: dict[str, int] = {}
    if not args.no_thumbs:
        # Still run the generator so cached paths are returned in thumb_map;
        # make_thumb is a cheap mtime check for files already covered.
        thumb_map, status_counts = generate_thumbs(
            [f.path for f in files],
            thumbs_dir,
            workers=workers,
        )
    else:
        # Even with --no-thumbs, reuse any existing cache files in the manifest.
        for f in files:
            tp = thumb_path_for(f.path, thumbs_dir)
            if tp.exists():
                thumb_map[f.path] = tp

    duration_map = ensure_durations(
        [f.path for f in files],
        thumbs_dir,
        workers=workers if not args.no_thumbs else DEFAULT_WORKERS,
    )

    entries: list[dict] = []
    for f in files:
        thumb_fi = None
        tp = thumb_map.get(f.path)
        if tp is not None and tp.exists():
            thumb_fi = make_file_info(tp, root, kind=KIND_THUMB)
        entry = make_entry(
            f, thumb=thumb_fi, duration=duration_map.get(f.path),
        )
        if entry is not None:
            entries.append(entry)

    entries.sort(key=lambda e: e["mtime"], reverse=True)
    stats = build_stats(entries, total_files=len(files))

    out_html = write_outputs(
        entries, stats, root=root, title=args.title, out_dir=out_dir,
    )
    extras = {}
    if status_counts:
        extras["Thumbs"] = (
            f"ok={status_counts.get('ok', 0)} "
            f"cached={status_counts.get('cached', 0)} "
            f"ffmpeg={status_counts.get('ffmpeg', 0)} "
            f"fail={status_counts.get('fail', 0)} "
            f"skipped={status_counts.get('skipped', 0)}"
        )
    print_summary(entries, stats, title=args.title, out_html=out_html,
                  extras=extras or None)

    if args.no_serve:
        return 0

    return serve_directory(
        root,
        bind=args.bind,
        port=args.port,
        open_path=out_html.name,
    )


if __name__ == "__main__":
    raise SystemExit(main())
