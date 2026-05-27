# AutoHotkey

AutoHotkey v2 scripts for global hotkeys and per-app bindings.

## Layout

```
AutoHotkey/
  main.ahk              Entry point — run this (or compile it)
  includes/
    env.ahk             Paths, constants, config loading
    functions.ahk       Shared helpers
  hotkeys/              Global shortcuts (always active)
  apps/                 Window-specific scripts (#HotIf)
  config/
    local.example.ini   Template for machine settings
    local.ini           Your copy (gitignored)
```

## Quick start

1. Install [AutoHotkey v2](https://www.autohotkey.com/).
2. Copy `config/local.example.ini` to `config/local.ini` and edit if needed.
3. Add scripts under `hotkeys/` or `apps/`, then `#Include` them from `main.ahk`.
4. Run `main.ahk` (double-click or add to Startup).

## Conventions

- **One concern per file** — e.g. `hotkeys/media.ahk`, `apps/cursor.ahk`.
- **Shared logic** lives in `includes/functions.ahk`, not duplicated in hotkey files.
- **Callback functions** in v2 need a trailing `*` when unused: `MyFn(*) { ... }`.
- **Per-app bindings** use `#HotIf WinActive(...)` in `apps/`, not in global hotkeys.

## Startup (optional)

Create a shortcut to `main.ahk` in:

`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`

Or run once at login via Task Scheduler.
