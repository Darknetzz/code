# Prereq Doctor

CLI tool that checks whether common development and Windows admin prerequisites are installed and reachable on `PATH`.

## Built-in checks

| Id | Label | Required |
|----|-------|----------|
| `git` | Git | yes |
| `rustc` | Rust compiler | yes |
| `cargo` | Cargo | yes |
| `python` | Python (`py`, `python`, or `python3`) | yes |
| `gh` | GitHub CLI | no |
| `node` | Node.js | no |
| `ping` | Ping utility | yes |
| `powershell` | PowerShell | yes (Windows only) |
| `rsat-ad` | RSAT Active Directory module | no (Windows only) |

## Build

```powershell
cd Rust/prereq-doctor
cargo build --release
```

## Quick start

```powershell
cargo run --release
cargo run --release -- --only git --only python
cargo run --release -- --config config.example.yaml
cargo run --release -- --json
cargo run --release -- --strict
```

## CLI options

- `--config <path>`: YAML file with extra command checks
- `--only <id>`: run only selected checks (repeatable)
- `--json`: emit JSON report
- `--strict`: treat optional check failures as a non-zero exit code

## Config format

See `config.example.yaml`. Custom checks try each command in `commands` until one succeeds.

## Exit codes

- `0`: all required checks passed
- `1`: one or more required checks failed (or optional checks when `--strict` is set)
- `2`: runtime/config/argument error
