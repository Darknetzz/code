# Zig

Scripts and projects in Zig.

| Subdirectory | Description |
|-------------|-------------|
| [hello](hello/) | Minimal Zig CLI that prints a greeting. See [hello/README.md](hello/README.md) for details. |
| [zcommon](zcommon/) | Shared helpers for the Zig CLIs (Windows console UTF-8). See [zcommon/README.md](zcommon/README.md) for details. |
| [zlink](zlink/) | Windows CLI for file/dir symlinks, junctions, and hard links. See [zlink/README.md](zlink/README.md) for details. |
| [zwhich](zwhich/) | PATH lookup that lists every match and marks which entry wins. See [zwhich/README.md](zwhich/README.md) for details. |


## Planned tools

These are queued after `zlink`. Each should stay a small Windows-friendly CLI with a project README.

| Project | Status | Idea |
|---------|--------|------|
| [zlink](zlink/) | started | Native Win32 symlink / junction / hardlink CLI (port of `Python/pylink`) |
| [zwhich](zwhich/) | started | PATH lookup that shows every match and which entry wins |
| zhex | planned | Hex dump of files or stdin (`offset`, `length`, ASCII gutter) |
| zpe | planned | Inspect Windows PE headers (machine, sections, imports) |
| zwatch | planned | Wait until a path appears or changes, then exit or run a command |
