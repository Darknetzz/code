# refreshenv

Windows CLI that reloads User and Machine environment variables from the registry and either spawns a new shell (in a new window) with that env or emits shell commands so the current session can apply them.

## Build

```bash
go build -o refreshenv.exe .
```

## Usage

```text
refreshenv [options]
```

## Options

| Flag | Description |
|------|-------------|
| `-shell` | Spawn a new shell with refreshed env (default: true). Use `-shell=false` to only load into this process and exit. |
| `-pwsh` | Prefer spawning PowerShell instead of cmd (default: auto when `PSModulePath` is set). |
| `-emit` | Print shell commands to stdout so the **current** shell can eval them (e.g. `refreshenv -emit \| iex` in PowerShell). No new window. |

## Behavior

- Reads **User** and **Machine** env from the Windows registry; **Path** is Machine + User combined.
- **Default:** Spawns a new shell in a **new console window** (PowerShell or cmd, auto-detected) with the refreshed env and exits, so the calling window is not nested.
- **`-emit`:** Outputs `$env:Name = 'value'; ...` (PowerShell) or `set "Name=value"` (cmd) so you can run e.g. `refreshenv -emit | Invoke-Expression` in the **current** session.

## Examples

```powershell
# New window with refreshed env (no nesting)
refreshenv.exe

# Refresh env in the current PowerShell session
refreshenv.exe -emit | iex

# Helper in profile: function refreshenv { refreshenv.exe -emit | iex }
```

```cmd
refreshenv.exe
```
