"""Directory scanning and size formatting."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pytree_lib.models import DirInfo, DirSummary, ProgressCb, ScanStats, format_size

__all__ = ["format_size", "scan_directory", "get_dir_size"]


def scan_directory(
    path: Path,
    max_depth: Optional[int] = None,
    current_depth: int = 0,
    *,
    stats: Optional[ScanStats] = None,
    progress_cb: Optional[ProgressCb] = None,
) -> DirInfo:
    if stats is None:
        stats = ScanStats()
    total_size = 0
    file_count = 0
    dir_count = 0
    children: list[DirInfo] = []
    error = None

    if progress_cb is not None:
        stats.current = str(path)
        progress_cb(stats)

    try:
        with os.scandir(path) as it:
            entries = list(it)
    except PermissionError:
        error = "Permission denied"
        entries = []
    except OSError as e:
        error = str(e)
        entries = []

    for entry in entries:
        if entry.is_symlink():
            continue
        item = Path(entry.path)
        try:
            if entry.is_file(follow_symlinks=False):
                sz = entry.stat(follow_symlinks=False).st_size
                total_size += sz
                file_count += 1
                stats.files += 1
                stats.size += sz
                if progress_cb is not None:
                    progress_cb(stats)
                children.append(
                    DirInfo(
                        path=item,
                        size=sz,
                        file_count=1,
                        dir_count=0,
                        children=[],
                    )
                )
            elif entry.is_dir(follow_symlinks=False):
                dir_count += 1
                stats.dirs += 1
                if max_depth is None or current_depth < max_depth:
                    child_info = scan_directory(
                        item,
                        max_depth,
                        current_depth + 1,
                        stats=stats,
                        progress_cb=progress_cb,
                    )
                    children.append(child_info)
                    total_size += child_info.size
                    file_count += child_info.file_count
                    dir_count += child_info.dir_count
                else:
                    summary = get_dir_size(item, stats=stats, progress_cb=progress_cb)
                    child_info = DirInfo(
                        path=item,
                        size=summary.size,
                        file_count=summary.files,
                        dir_count=summary.dirs,
                        children=[],
                        error=summary.error,
                    )
                    children.append(child_info)
                    total_size += summary.size
                    file_count += summary.files
                    dir_count += summary.dirs
        except PermissionError:
            continue
        except OSError:
            continue

    children.sort(key=lambda x: x.size, reverse=True)
    return DirInfo(
        path=path,
        size=total_size,
        file_count=file_count,
        dir_count=dir_count,
        children=children,
        error=error,
    )


def get_dir_size(
    path: Path,
    *,
    stats: Optional[ScanStats] = None,
    progress_cb: Optional[ProgressCb] = None,
) -> DirSummary:
    summary = DirSummary()
    try:
        for root, dirnames, filenames in os.walk(path, followlinks=False):
            root_path = Path(root)
            for name in filenames:
                item = root_path / name
                try:
                    if item.is_symlink():
                        continue
                    sz = item.stat().st_size
                    summary.size += sz
                    summary.files += 1
                    if stats is not None:
                        stats.files += 1
                        stats.size += sz
                        if progress_cb is not None:
                            progress_cb(stats)
                except OSError:
                    continue
            summary.dirs += len(dirnames)
            if stats is not None:
                stats.dirs += len(dirnames)
    except OSError as e:
        summary.error = f"{type(e).__name__}: {e}"
    return summary
