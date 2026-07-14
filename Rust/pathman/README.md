# pathman

Cross-platform GUI for viewing and editing **user** and **system (machine)** PATH entries and other environment variables.

## Modes

| Tab | Meaning |
|-----|---------|
| **PATH** | Dedicated PATH editor (reorder, dedupe, folder picker, duplicate warnings) |
| **Environment** | All other environment variables as name/value rows |

Both modes share the same scope tabs:

| Scope | Meaning |
|-------|---------|
| **Effective** | Merged machine → user view (editable; may differ from a login-shell `echo $VAR`) |
| **User** | Per-user store |
| **System** | Machine-wide store |

PATH is edited only in the **PATH** tab. The Environment tab excludes `Path`/`PATH`.

## Run

```bash
cargo run --release
# or open the built binary from Rust/pathman/target/release/
```

## Windows

- User and system variables are read from `HKCU\Environment` and `HKLM\...\Environment`.
- Saving **System** scope may trigger UAC elevation.
- Values containing `%VAR%` are stored as `REG_EXPAND_SZ`.
- Internal helper: `pathman --apply-machine <file>` (used after elevation).

## Unix / macOS

- User PATH and environment variables share a managed shell snippet (see **Settings** in the app when on the PATH tab, User scope).
- Managed block format:

```sh
# --- pathman managed BEGIN ---
export PATH="prefix:$PATH"
export MY_VAR="hello"
# --- pathman managed END ---
```

- System PATH: macOS `/etc/paths.d/99-pathman`; Linux `/etc/profile.d/pathman.sh`
- System other env vars: macOS `/etc/profile.d/99-pathman-env`; Linux non-PATH exports in `/etc/profile.d/pathman.sh`
- System saves use `pkexec` / `osascript`; config in `~/.config/pathman/pathman.toml`.
- Only variables inside pathman-managed files are editable (same limitation as PATH today).

## Config

`~/.config/pathman/pathman.toml` (or platform config dir):

- `user_shell_path` — file containing the user managed block (PATH + env exports)
- `skip_remove_confirmation` — skip remove-row confirm dialog

## Build

```bash
cargo build --release
```

## Tests

```bash
cargo test
```

### Manual test checklist

- **Windows:** add/edit/delete user env var; same for system (UAC); Effective cross-store edit; PATH tab unchanged
- **Linux:** user file multi-export; system profile.d; pkexec path
- **macOS:** user file; system `/etc/profile.d/99-pathman-env`
