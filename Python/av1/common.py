"""Shared constants and formatting helpers for av1 and av1-verify."""
from __future__ import annotations

import platform
import sys

SUPPORTED_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv")


def ensure_utf8_stdio() -> None:
    """Force UTF-8 stdout/stderr on Windows when attached to a TTY."""
    if platform.system() != "Windows":
        return
    if not (sys.stdout.isatty() and sys.stderr.isatty()):
        return
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def format_duration(seconds: float | None) -> str:
    """Format duration in seconds to HH:MM:SS.mmm format."""
    if seconds is None:
        return "N/A"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{int(minutes):02d}:{secs:06.3f}"


def format_size(bytes_amount: int) -> str:
    """Format file size in bytes to human-readable format."""
    if bytes_amount >= 1024**3:
        return f"{bytes_amount / (1024**3):.2f} GB"
    if bytes_amount >= 1024**2:
        return f"{bytes_amount / (1024**2):.2f} MB"
    if bytes_amount >= 1024:
        return f"{bytes_amount / 1024:.2f} KB"
    return f"{bytes_amount} B"
