#!/usr/bin/env python3
"""
Generate root README.md and update/create README.md in each top-level subdirectory
in Go-style format (title, description, table of subdirectories). Works on Windows and Linux.
Run from the repository root: python generate_readmes.py
"""

from pathlib import Path
import re
import sys

# Directories to skip when listing subdirs (build/output/hidden)
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
}


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
        p for p in path.iterdir()
        if p.is_dir() and not is_skipped(p.name)
    )


def extract_description(readme_path: Path, dir_name: str) -> str:
    """
    From README.md, get the first paragraph after the main # Title line.
    Used as the "Description" in parent's table.
    """
    if not readme_path.is_file():
        return "—"
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "—"
    # Match # DirName or # dir_name, then take next non-empty block until ## or end
    title_pattern = re.compile(
        r"^#\s+.+$",
        re.MULTILINE,
    )
    lines = text.splitlines()
    found_title = False
    description_lines = []
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


def get_existing_intro(readme_path: Path, dir_display_name: str) -> str | None:
    """
    If README exists, return the first paragraph after # Title as intro.
    Otherwise return None (caller will use default).
    """
    if not readme_path.is_file():
        return None
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    found_title = False
    intro_lines = []
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


def humanize_dir_name(name: str) -> str:
    """e.g. python -> Python, PowerShell -> PowerShell (preserve rest of casing)."""
    if not name:
        return name
    return name[0].upper() + name[1:]


def build_root_readme(root: Path) -> str:
    subdirs = get_direct_subdirs(root)
    title = root.name if root.name else "code"
    lines = [
        f"# {title}",
        "",
        "Different scripts in different languages for different purposes.",
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


def build_subdir_readme(
    dir_path: Path,
    subdirs: list[Path],
    parent_is_root: bool,
) -> str:
    """Build Go-style README: title, description, table of subdirectories."""
    name = dir_path.name
    display_name = humanize_dir_name(name)
    readme_path = dir_path / "README.md"

    intro = get_existing_intro(readme_path, display_name)
    if not intro:
        intro = f"Scripts and projects in {display_name}."

    lines = [
        f"# {display_name}",
        "",
        intro,
        "",
    ]

    if subdirs:
        lines.append("| Subdirectory | Description |")
        lines.append("|-------------|-------------|")
        for sub in subdirs:
            sub_readme = sub / "README.md"
            desc = extract_description(sub_readme, sub.name)
            # If subdir has README with more details, link it when description is long
            sub_link = f"[{sub.name}/README.md]({sub.name}/README.md)"
            if desc != "—" and len(desc) > 80:
                desc = desc[:77].rstrip() + "..."
                if sub_readme.is_file():
                    desc += f" See {sub_link} for details."
            elif sub_readme.is_file() and desc != "—":
                desc += f" See {sub_link} for details."
            lines.append(f"| **{sub.name}** | {desc} |")
        lines.append("")

    # Optional footer for Go
    if name.lower() == "go" and subdirs:
        lines.append("Each project has its own `go.mod`. Build from the project directory, e.g. `go build -o b64 .` in `b64/`.")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    root = get_repo_root()
    print(f"Repository root: {root}")

    # 1. Root README
    root_readme = root / "README.md"
    content = build_root_readme(root)
    root_readme.write_text(content, encoding="utf-8")
    print(f"Updated: {root_readme.relative_to(root)}")

    # 2. Each top-level subdirectory
    for subdir in get_direct_subdirs(root):
        children = get_direct_subdirs(subdir)
        content = build_subdir_readme(subdir, children, parent_is_root=True)
        readme_path = subdir / "README.md"
        readme_path.write_text(content, encoding="utf-8")
        print(f"Updated: {readme_path.relative_to(root)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
