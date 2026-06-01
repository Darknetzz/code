"""Data structures shared by CLI, TUI, and report renderers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, List, NamedTuple, Optional, Tuple

def format_size(size: int) -> str:
    size_float = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_float < 1024.0:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    return f"{size_float:.1f} PB"


@dataclass
class DirInfo:
    """Directory information with size and file counts."""
    path: Path
    size: int
    file_count: int
    dir_count: int
    children: List["DirInfo"]
    error: Optional[str] = None

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)

    def format_size(self) -> str:
        return format_size(self.size)


def entry_is_directory(info: DirInfo) -> bool:
    try:
        return info.path.is_dir()
    except OSError:
        return bool(info.children)


def child_count_cells(
    info: DirInfo, *, empty: str = "", fmt: str = "{:,}"
) -> Tuple[str, str]:
    if not entry_is_directory(info):
        return (empty, empty)
    return (fmt.format(info.file_count), fmt.format(info.dir_count))


class ChildRow(NamedTuple):
    index: int
    child: DirInfo
    size_str: str
    files_str: str
    dirs_str: str
    is_dir: bool


def iter_child_rows(dir_info: DirInfo, limit: int) -> Iterator[ChildRow]:
    for i, child in enumerate(dir_info.children[:limit], 1):
        files_s, dirs_s = child_count_cells(child)
        yield ChildRow(
            index=i,
            child=child,
            size_str=format_size(child.size),
            files_str=files_s,
            dirs_str=dirs_s,
            is_dir=entry_is_directory(child),
        )


@dataclass
class ScanStats:
    files: int = 0
    dirs: int = 0
    size: int = 0
    current: str = ""


ProgressCb = Callable[[ScanStats], None]


@dataclass
class DirSummary:
    size: int = 0
    files: int = 0
    dirs: int = 0
    error: Optional[str] = None
