#!/usr/bin/env python3
"""Generate a static HTML gallery from any directory tree of media files.

Recursively walks the chosen directory, picks up images and videos by
extension, and emits a self-contained ``gallery.html`` plus supporting assets
in a ``gallery/`` subfolder via the shared :mod:`_core` module.

The page works over ``file://`` (no web server needed). Tabs are auto-built
from the first-level subfolders of the scanned root, so e.g.::

    D:\\Photos\\
      Vacation2024\\...
      Screenshots\\...
      CameraRoll\\...

gets three tabs. If there's only one top-level folder (or none), the tab bar
is hidden and you get just the year/month/type filters.

Usage:
    python pygallery.py                      # scan current directory
    python pygallery.py D:\\Photos           # scan a specific folder
    python pygallery.py D:\\Photos --title "My Photos"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from _core import (
    FileInfo,
    KIND_STANDALONE,
    MEDIA_EXTS,
    build_stats,
    make_entry,
    make_file_info,
    print_summary,
    write_outputs,
)


# Directory names we never descend into. Contains the output folder plus a
# conservative set of common junk dirs so scanning a repo or system folder
# doesn't churn through tens of thousands of irrelevant files.
DEFAULT_SKIP_DIRS = {
    "gallery",         # our own output
    "__pycache__",
    "node_modules",
    ".git", ".hg", ".svn",
    ".idea", ".vscode",
    "System Volume Information", "$RECYCLE.BIN",
}


def scan_tree(root: Path, out_dir: Path,
              skip_dirs: set[str] = DEFAULT_SKIP_DIRS) -> list[FileInfo]:
    """Recursively collect media files under ``root`` as :class:`FileInfo`.

    Skips the generated output directory, dot-directories, and a small set of
    well-known junk folders. Does not follow symlinks.
    """
    files: list[FileInfo] = []
    for dirpath_str, dirnames, filenames in os.walk(root, followlinks=False):
        dirpath = Path(dirpath_str)

        # Prune so we don't descend into noisy / irrelevant subtrees.
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in skip_dirs
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
    parser.add_argument("root", nargs="?", default=".",
                        help="Directory to scan recursively (default: current dir).")
    parser.add_argument("--title", default="Media Gallery",
                        help="Page title shown in the header (default: 'Media Gallery').")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1

    out_dir = root / "gallery"
    files = scan_tree(root, out_dir)
    if not files:
        print(f"No media files found in {root}", file=sys.stderr)
        print(f"Looking for extensions: {', '.join(sorted(MEDIA_EXTS))}", file=sys.stderr)
        return 1

    entries = [e for e in (make_entry(f) for f in files) if e]
    entries.sort(key=lambda e: e["mtime"], reverse=True)
    stats = build_stats(entries, total_files=len(files))

    out_html = write_outputs(entries, stats, root=root, title=args.title)
    print_summary(entries, stats, title=args.title, out_html=out_html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
