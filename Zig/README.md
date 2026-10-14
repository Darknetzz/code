# Zig

Scripts and projects in Zig.

| Subdirectory | Description |
|-------------|-------------|
| [zcommon](zcommon/) | Shared helpers for the Zig CLIs (Windows console UTF-8 and ANSI color). See [zcommon/README.md](zcommon/README.md) for details. |
| [zgen](zgen/) | Generate random strings of length N from presets or a custom charset. See [zgen/README.md](zgen/README.md) for details. |
| [zlink](zlink/) | Windows CLI for file/dir symlinks, junctions, and hard links. See [zlink/README.md](zlink/README.md) for details. |
| [zwhich](zwhich/) | PATH lookup that lists every match and marks which entry wins. See [zwhich/README.md](zwhich/README.md) for details. |


## Planned tools

These are queued after `zlink`. Each should stay a small Windows-friendly CLI with a project README.

| Project | Status | Idea |
|---------|--------|------|
| [zlink](zlink/) | started | Native Win32 symlink / junction / hardlink CLI (port of `Python/pylink`) |
| [zwhich](zwhich/) | started | PATH lookup that shows every match and which entry wins |
| [zgen](zgen/) | started | Random string generator with charset presets (CSPRNG by default) |
| zhex | planned | Hex dump of files or stdin (`offset`, `length`, ASCII gutter) |
| zpe | planned | Inspect Windows PE headers (machine, sections, imports) |
| zwatch | planned | Wait until a path appears or changes, then exit or run a command |

## GitLab CI → setupfiles

On changes under `Zig/` (or a manual web pipeline), GitLab CI on `gitlab.roste.org:kriss/code`:

1. Builds Linux amd64 **ReleaseSafe** binaries for `zgen` and `zwhich`
2. Commits them to `setupfiles` `main` at `Linux/opt/setupfiles/bin/`

Publish uses SSH to `gitlab.roste.org:2222` (`SETUPFILES_SSH_PRIVATE_KEY` deploy key), with optional HTTPS fallback (`SETUPFILES_GITLAB_TOKEN`). Do not use `gitlab01:22` — that is host SSH, not GitLab. Scripts: [`!scripts/ci-install-zig.sh`](../!scripts/ci-install-zig.sh), [`!scripts/publish-zig-bins-to-setupfiles.sh`](../!scripts/publish-zig-bins-to-setupfiles.sh).
