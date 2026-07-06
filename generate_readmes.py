#!/usr/bin/env python3
"""
Generate root README.md and update README.md indexes in language/domain folders.

Run from the repository root:

    python generate_readmes.py

See AGENTS.md for when to run this and which READMEs are managed manually.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

# Directories to skip when listing subdirs (build/output/hidden/internal)
SKIP_DIRS = {
    ".git",
    ".vscode",
    "__pycache__",
    "target",
    "node_modules",
    "dist",
    ".venv",
    "venv",
    "Lib",
    "Include",
    "Scripts",
    "python-win",
    "python-linux",
    "apps",
    "config",
    "hotkeys",
    "includes",
}

# Omit from the repo root index (not language/domain workspaces)
SKIP_ROOT_DIRS = {
    "!scripts",
    ".cursor",
    ".github",
    ".vscode",
}

# READMEs with custom layout or curated script lists — do not overwrite
PRESERVE_README_DIRS = {
    "AutoHotkey",
    "PowerShell",
    "Shell",
}

# Subdirs that exist on disk but should not appear in parent indexes
SKIP_INDEX_SUBDIRS = {
    "rustdl",  # moved to external repo; keep manual table row instead
}

SUBDIR_ROW_RE = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)/?\)\s*\|")
SEPARATOR_ROW_RE = re.compile(r"^\|\s*[-:|]+\s*\|")

GO_BUILD_NOTE = (
    "Each project has its own `go.mod`. Build from the project directory, "
    "e.g. `go build -o b64 .` in `b64/`."
)


def get_repo_root() -> Path:
    """Assume script is run from repo root, or find it by .git."""
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        return cwd
    script_dir = Path(__file__).resolve().parent
    if (script_dir / ".git").exists():
        return script_dir
    return cwd


def is_skipped(name: str) -> bool:
    return name.startswith(".") or name in SKIP_DIRS


def get_direct_subdirs(path: Path) -> list[Path]:
    """Return direct subdirectories, excluding skipped ones."""
    if not path.is_dir():
        return []
    return sorted(
        p
        for p in path.iterdir()
        if p.is_dir() and not is_skipped(p.name) and p.name not in SKIP_INDEX_SUBDIRS
    )


def extract_description(readme_path: Path) -> str:
    """First paragraph after the main # Title line, for parent index tables."""
    if not readme_path.is_file():
        return "—"
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "—"
    lines = text.splitlines()
    found_title = False
    description_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#\s+", line):
            if found_title:
                break
            found_title = True
            continue
        if found_title:
            if stripped.startswith("##") or stripped.startswith("|"):
                break
            if stripped:
                description_lines.append(stripped)
            elif description_lines:
                break
    if not description_lines:
        return "—"
    return " ".join(description_lines).strip()


def get_existing_intro(readme_path: Path) -> str | None:
    """First paragraph after # Title; None if README missing or empty intro."""
    if not readme_path.is_file():
        return None
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    found_title = False
    intro_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#\s+", line):
            if found_title:
                break
            found_title = True
            continue
        if found_title:
            if stripped.startswith("##") or stripped.startswith("|"):
                break
            if stripped.startswith("[//]:") or stripped.startswith("<!--"):
                continue
            if stripped:
                intro_lines.append(stripped)
            elif intro_lines:
                break
    if not intro_lines:
        return None
    return " ".join(intro_lines).strip()


def parse_readme_tail(readme_path: Path) -> tuple[list[str], str]:
    """
    Return (manual_table_rows, body_after_table) from an existing README.

    Manual rows are table lines whose first column is not a [name](name/) subdir link
    (e.g. external-project notes like rustdl).
    """
    if not readme_path.is_file():
        return [], ""
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], ""

    lines = text.splitlines()
    table_start: int | None = None
    table_end: int | None = None
    manual_rows: list[str] = []

    for i, line in enumerate(lines):
        if line.strip().startswith("|") and table_start is None:
            if i + 1 < len(lines) and re.match(r"^\|\s*[-:|]+\s*\|", lines[i + 1]):
                table_start = i
                continue
        if table_start is not None and table_end is None:
            if line.strip().startswith("|"):
                stripped = line.strip()
                if SEPARATOR_ROW_RE.match(stripped):
                    continue
                if not SUBDIR_ROW_RE.match(stripped):
                    manual_rows.append(line.rstrip())
            else:
                table_end = i
                break

    if table_start is not None and table_end is None:
        table_end = len(lines)

    body = ""
    if table_end is not None:
        body = "\n".join(lines[table_end:]).strip()
        if body:
            body = "\n" + body + "\n"

    return manual_rows, body


def strip_go_build_note(body: str) -> str:
    """Remove Go build boilerplate so regeneration does not duplicate it."""
    if not body:
        return body
    lines = body.splitlines()
    kept: list[str] = []
    for line in lines:
        if line.strip() == GO_BUILD_NOTE:
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def humanize_dir_name(name: str) -> str:
    if not name:
        return name
    return name[0].upper() + name[1:]


def format_subdir_description(sub: Path, desc: str) -> str:
    sub_readme = sub / "README.md"
    sub_link = f"[{sub.name}/README.md]({sub.name}/README.md)"
    if desc != "—" and len(desc) > 80:
        desc = desc[:77].rstrip() + "..."
        if sub_readme.is_file():
            desc += f" See {sub_link} for details."
    elif sub_readme.is_file() and desc != "—":
        desc += f" See {sub_link} for details."
    return desc


def build_subdir_table_rows(subdirs: list[Path]) -> list[str]:
    rows = [
        "| Subdirectory | Description |",
        "|-------------|-------------|",
    ]
    for sub in subdirs:
        desc = format_subdir_description(sub, extract_description(sub / "README.md"))
        rows.append(f"| [{sub.name}]({sub.name}/) | {desc} |")
    return rows


def build_root_readme(root: Path) -> str:
    subdirs = [
        d for d in get_direct_subdirs(root) if d.name not in SKIP_ROOT_DIRS
    ]
    title = root.name if root.name else "code"
    readme_path = root / "README.md"
    intro = get_existing_intro(readme_path) or (
        "Scripts and CLI tools in various languages "
        "(AutoHotkey, Go, Lua, PHP, PowerShell, Python, Rust, Shell)."
    )

    lines = [
        f"# {title}",
        "",
        intro,
        "",
        "## Index",
        "",
        "| Directory |",
        "|-----------|",
    ]
    for d in subdirs:
        lines.append(f"| [{humanize_dir_name(d.name)}]({d.name}/) |")
    lines.append("")
    return "\n".join(lines)


def build_subdir_readme(dir_path: Path, subdirs: list[Path]) -> str:
    name = dir_path.name
    display_name = humanize_dir_name(name)
    readme_path = dir_path / "README.md"

    intro = get_existing_intro(readme_path) or f"Scripts and projects in {display_name}."
    manual_rows, body = parse_readme_tail(readme_path)

    lines = [
        f"# {display_name}",
        "",
        intro,
        "",
    ]

    if subdirs:
        lines.extend(build_subdir_table_rows(subdirs))
        for row in manual_rows:
            lines.append(row)
        lines.append("")

    if name.lower() == "go" and subdirs:
        lines.append(GO_BUILD_NOTE)
        lines.append("")

    if body:
        if name.lower() == "go":
            body = strip_go_build_note(body)
        if body:
            lines.append(body.rstrip())
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    root = get_repo_root()
    print(f"Repository root: {root}")

    root_readme = root / "README.md"
    root_readme.write_text(build_root_readme(root), encoding="utf-8")
    print(f"Updated: {root_readme.relative_to(root)}")

    for subdir in get_direct_subdirs(root):
        if subdir.name in SKIP_ROOT_DIRS:
            continue
        if subdir.name in PRESERVE_README_DIRS:
            print(f"Skipped (custom README): {subdir.name}/README.md")
            continue

        children = get_direct_subdirs(subdir)
        readme_path = subdir / "README.md"
        readme_path.write_text(build_subdir_readme(subdir, children), encoding="utf-8")
        print(f"Updated: {readme_path.relative_to(root)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
