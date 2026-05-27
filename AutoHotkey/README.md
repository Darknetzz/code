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
4. Run `main.ahk` (double-click or add to Startup). A help panel opens with hotkey reference and Reload / Edit / Hide / Exit.

   Silent startup (no window): `main.ahk --silent` or `main.ahk -s`

## Help panel

| Action | Hotkey |
|--------|--------|
| Show help panel | Win+Ctrl+H |

Defined in [`includes/helpGui.ahk`](includes/helpGui.ahk). Closing the window hides it; hotkeys keep running. Use **Exit** to quit the script.

## Case transforms

Select text, then press a hotkey to copy, transform, and paste in place. Original clipboard content is restored after ~150ms.

| Action | Hotkey | Example |
|--------|--------|---------|
| UPPERCASE | Win+Ctrl+U | `hello` → `HELLO` |
| lowercase | Win+Ctrl+L | `HELLO` → `hello` |
| Title Case | Win+Ctrl+T | `hello world` → `Hello World` |
| rAnDoM cAsE | Win+Ctrl+R | `hello` → `hElLo` (varies) |
| slug | Win+Ctrl+S | `Hello World!` → `hello-world` |

Logic: [`includes/stringCase.ahk`](includes/stringCase.ahk). Hotkeys: [`hotkeys/case-transform.ahk`](hotkeys/case-transform.ahk).

## Conventions

- **One concern per file** — e.g. `hotkeys/media.ahk`, `apps/cursor.ahk`.
- **Shared logic** lives in `includes/functions.ahk`, not duplicated in hotkey files.
- **Callback functions** in v2 need a trailing `*` when unused: `MyFn(*) { ... }`.
- **Per-app bindings** use `#HotIf WinActive(...)` in `apps/`, not in global hotkeys.

## Startup (optional)

Create a shortcut to `main.ahk` in:

`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`

Or run once at login via Task Scheduler.
