"""Interactive CLI prompts with optional readline path completion.

Importing readline also enables emacs-style line editing (left/right arrows,
Ctrl-A/E, etc.) for ``input()`` on platforms where it is available.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import readline
except ImportError:  # pragma: no cover - Windows without pyreadline3
    try:
        import pyreadline3 as readline  # type: ignore
    except ImportError:
        readline = None  # type: ignore[assignment]


_matches: list[str] = []


def _to_display_path(abs_or_norm: str, typed: str) -> str:
    """Map a filesystem path back into the form the user is typing (keep ``~``)."""
    abs_or_norm = abs_or_norm.replace("\\", "/")
    typed = typed.replace("\\", "/")
    home = os.path.expanduser("~").replace("\\", "/")

    if typed.startswith("~"):
        if abs_or_norm == home:
            return "~"
        if abs_or_norm.startswith(home + "/"):
            return "~/" + abs_or_norm[len(home) + 1 :]
    return abs_or_norm if os.path.isabs(typed) else abs_or_norm


def _list_path_matches(text: str) -> list[str]:
    text = text or ""
    expanded = os.path.expanduser(text)

    if text.endswith(("/", "\\")):
        directory = expanded
        partial = ""
    else:
        directory = os.path.dirname(expanded)
        partial = os.path.basename(expanded)
        if not directory:
            directory = "."

    try:
        names = os.listdir(directory)
    except OSError:
        return []

    # Prefix to put before each name in the completion string.
    if text.endswith(("/", "\\")):
        prefix = text
    else:
        parent = os.path.dirname(text)
        if parent:
            prefix = parent.rstrip("/\\") + "/"
        elif text.startswith("~") and "/" not in text.replace("\\", "/"):
            # Typing "~" or "~user" — rare; fall through to expanded listing.
            prefix = ""
        else:
            prefix = ""

    matches: list[str] = []
    for name in sorted(names, key=str.casefold):
        if partial and not name.lower().startswith(partial.lower()):
            continue
        if not partial and name.startswith("."):
            continue

        if directory in (".", ""):
            full = os.path.join(os.getcwd(), name) if directory == "." else name
            shown = prefix + name
        else:
            full = os.path.join(directory, name)
            if prefix:
                shown = prefix + name
            elif text.startswith("~"):
                shown = _to_display_path(full, text)
            else:
                shown = full if os.path.isabs(text) else name

        shown = shown.replace("\\", "/")
        if os.path.isdir(full):
            shown = shown.rstrip("/") + "/"
        matches.append(shown)
    return matches


def _path_completer(text: str, state: int) -> str | None:
    global _matches
    if state == 0:
        try:
            line = readline.get_line_buffer()
            beg = readline.get_begidx()
            end = readline.get_endidx()
            text = line[beg:end]
        except Exception:
            pass
        _matches = _list_path_matches(text)
    try:
        return _matches[state]
    except IndexError:
        return None


def ensure_line_editing() -> None:
    """Best-effort: load readline so arrow keys work in ``input()``."""
    if readline is None:
        return
    try:
        readline.parse_and_bind("set editing-mode emacs")
    except Exception:
        pass


@contextmanager
def path_completion_enabled() -> Iterator[None]:
    """Install a filesystem path completer for the duration of the block."""
    if readline is None:
        yield
        return

    previous = readline.get_completer()
    try:
        prev_delims = readline.get_completer_delims()
    except Exception:
        prev_delims = None

    readline.set_completer(_path_completer)
    # Whole path is one word so Tab completes through directories.
    try:
        readline.set_completer_delims(" \t\n")
    except Exception:
        pass
    try:
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set editing-mode emacs")
        # libedit (macOS / some BSDs)
        readline.parse_and_bind("bind ^I rl_complete")
    except Exception:
        pass

    try:
        yield
    finally:
        readline.set_completer(previous)
        if prev_delims is not None:
            try:
                readline.set_completer_delims(prev_delims)
            except Exception:
                pass


def prompt_path(label: str, default: Path | None = None, *,
                must_exist: bool = False) -> Path:
    """Ask for a path on stdin; empty input keeps default when provided."""
    ensure_line_editing()
    with path_completion_enabled():
        while True:
            suffix = f" [{default}]" if default is not None else ""
            try:
                raw = input(f"{label}{suffix}: ").strip()
            except EOFError:
                if default is not None:
                    return default.expanduser().resolve()
                print("\nCancelled: no path provided.", file=sys.stderr)
                raise SystemExit(2) from None
            if not raw:
                if default is None:
                    print("Please enter a path.", file=sys.stderr)
                    continue
                value = default
            else:
                value = Path(raw).expanduser()
            try:
                value = value.resolve()
            except OSError as exc:
                print(f"Invalid path: {exc}", file=sys.stderr)
                continue
            if must_exist and not value.is_dir():
                print(f"Not a directory: {value}", file=sys.stderr)
                continue
            return value


def prompt_int(label: str, default: int, *, minimum: int = 1) -> int:
    ensure_line_editing()
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
