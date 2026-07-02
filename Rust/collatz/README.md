# collatz

CLI for the Collatz conjecture (3n+1) on arbitrary-size positive integers.

Uses a `u128` fast path for values that fit in native integers, with automatic fallback to [malachite](https://crates.io/crates/malachite) when intermediate values overflow or the input is larger than `u128`.

## Build

```powershell
cd Rust/collatz
cargo build --release
```

Release builds are recommended; the hot loop is integer arithmetic.

## Usage

```powershell
cargo run --release -- 27
cargo run --release -- 999999999999999999999999999999999
cargo run --release -- --steps-only 27
cargo run --release -- --show-sequence 27
cargo run --release -- --json 27
```

### Arguments

| Argument | Description |
|----------|-------------|
| `NUMBER` | Required. Positive decimal integer (any size). |

### Flags

| Flag | Description |
|------|-------------|
| `--steps-only` | Print only the step count (bare number). |
| `--show-sequence` | Print every value in the sequence, then the summary. |
| `--peak` | Include peak value when combined with `--steps-only`. |
| `--json` | Emit a JSON report (`start`, `steps`, `peak`, optional `sequence`). |

### Default output

```
steps: 111
peak: 9232
```

### Examples

```powershell
# Step count and peak (default)
.\target\release\collatz.exe 27

# Step count only
.\target\release\collatz.exe --steps-only 27

# Full sequence plus summary
.\target\release\collatz.exe --show-sequence 27

# Machine-readable output
.\target\release\collatz.exe --json 27
.\target\release\collatz.exe --json --show-sequence 27
```

Invalid input (empty, zero, negative, non-numeric) exits with code `1`.
