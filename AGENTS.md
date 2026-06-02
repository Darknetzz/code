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

## DNS/Network checker location

The DNS/network verification tool lives in:

- `Python/dns-net-check/dns_net_check.py`
- `Python/dns-net-check/checks/`
- `Python/dns-net-check/config.example.yaml`
- `Python/dns-net-check/requirements.txt`

## Running the DNS tool

From `Python/dns-net-check/`:

```powershell
python dns_net_check.py --config config.example.yaml --no-ping
```
