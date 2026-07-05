# Repository Structure Guide

This repository is a multi-language monorepo. Keep new work inside the language/domain folder instead of the repository root.

## Top-level layout

- `Python/`: Python scripts, projects, and shared Python tooling.
- `PowerShell/`: PowerShell modules and scripts.
- `Go/`, `Rust/`, `PHP/`, `Lua/`, `Shell/`, `AutoHotkey/`: language-specific workspaces.
- `.cursor/`, `.github/`, `.vscode/`: editor, automation, and CI metadata.
- `!scripts/`: repo-level utility scripts.

## Placement rules

- Put new Python projects under `Python/<project-name>/`.
- Keep project-local dependencies in `Python/<project-name>/requirements.txt`.
- Keep examples/configs in the same project directory.
- Avoid placing runnable project files directly in the repo root.

## README indexes

This repo uses layered `README.md` files as navigation indexes:

| File | Purpose |
|------|---------|
| [`README.md`](README.md) | Root index — links to each language/domain folder |
| `<Lang>/README.md` | Project index — table of subdirectories with one-line descriptions |
| `<Lang>/<project>/README.md` | Project docs — full usage, options, examples |

### Keep indexes in sync

After **adding, renaming, or removing** a project subdirectory under a language folder, regenerate the indexes:

```powershell
python generate_readmes.py
```

Run this from the repository root before committing structural changes. The script:

- Updates the root index and auto-managed language indexes (`Go/`, `Lua/`, `PHP/`, `Python/`, `Rust/`, etc.)
- Pulls one-line descriptions from each project's first README paragraph
- Preserves **manual table rows** (e.g. external-repo notes like `rustdl` in `Rust/README.md`)
- Preserves **custom READMEs** that are not simple indexes: `AutoHotkey/`, `PowerShell/`, `Shell/`

When adding a new project, also add a `README.md` in the project folder with a short intro paragraph under the `# Title` — that text becomes the parent's index description.

### Manual README exceptions

- **`AutoHotkey/README.md`** — full usage guide; do not run the generator over it (listed in `PRESERVE_README_DIRS` in `generate_readmes.py`).
- **`PowerShell/README.md`** and **`Shell/README.md`** — curated script lists, not subdirectory indexes.
- **`!scripts/`** — build helpers only; excluded from the root index.

## DNS/Network checker location

The DNS/network verification tool is available in Python and Rust:

**Python** (`Python/dns-net-check/`):

- `Python/dns-net-check/dns_net_check.py`
- `Python/dns-net-check/checks/`
- `Python/dns-net-check/config.example.yaml`
- `Python/dns-net-check/requirements.txt`

**Rust** (`Rust/dns-net-check/`):

- `Rust/dns-net-check/src/`
- `Rust/dns-net-check/config.example.yaml`

## Running the DNS tool

From `Python/dns-net-check/`:

```powershell
python dns_net_check.py --config config.example.yaml --no-ping
```

From `Rust/dns-net-check/`:

```powershell
cargo run --release -- --config config.example.yaml --no-ping
```

## Prereq doctor location

Development prerequisite checker:

- `Rust/prereq-doctor/src/`
- `Rust/prereq-doctor/config.example.yaml`

```powershell
cd Rust/prereq-doctor
cargo run --release
```
