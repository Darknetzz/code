# pathman

Cross-platform GUI for viewing and editing **user** and **system (machine)** PATH entries.

## Scopes

| Tab | Meaning |
|-----|---------|
| **Effective** | Merged machine → user PATH (editable; may differ from a login-shell `echo $PATH`) |
| **User** | Per-user PATH store |
| **System** | Machine-wide PATH (Windows: HKLM; Unix: managed block) |

## Run

```bash
cargo run --release
# or open the built binary from Rust/pathman/target/release/
```

## Windows

- Saving **System** PATH may trigger UAC elevation.
- Internal helper: `pathman --apply-machine <file>` (used after elevation).

## Unix / macOS

- User PATH is managed via a shell snippet (see **Settings** in the app).
- System PATH uses `pkexec` / `osascript` helpers; config in `~/.config/pathman/pathman.toml`.
- **Effective** view is not identical to your full login-shell PATH if the shell adds paths elsewhere.

## Config

`~/.config/pathman/pathman.toml` (or platform config dir):

- `user_shell_path` — file containing the user PATH block
- `skip_remove_confirmation` — skip remove-row confirm dialog

## Build

```bash
cargo build --release
```

## Tests

```bash
cargo test
```
