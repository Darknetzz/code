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
cargo run --release -- "2^54"
cargo run --release -- "12340*248"
cargo run --release -- 999999999999999999999999999999999
cargo run --release -- --steps-only 27
cargo run --release -- --show-sequence 27
cargo run --release -- --json 27
```

### Arguments

| Argument | Description |
|----------|-------------|
| `NUMBER` | Required. Positive decimal integer or arithmetic expression. |

Expressions support `+`, `-`, `*`, `/`, `^`, and parentheses. **Quote expressions in PowerShell** (e.g. `"935577^7777777"`) so operators are passed to the program correctly.

Powers are limited to exponent ≤ 1,000,000 and values with at most 500,000 decimal digits.

### Flags

| Flag | Description |
|------|-------------|
| `--steps-only` | Print only the step count (bare number). |
| `--show-sequence` | Print every value in the sequence, then the summary. |
| `--peak` | Include peak value when combined with `--steps-only`. |
| `--json` | Emit a JSON report (`start`, `steps`, `peak`, optional `sequence`). |
| `--progress` | Show live step/current/peak updates on stderr. |
| `--no-progress` | Disable progress output (including the default on interactive stderr). |

### Progress

Progress and status messages are written to **stderr** when stderr is a terminal (disabled with `--json`, `--no-progress`, or non-interactive stderr). Step progress uses bit counts for huge integers to avoid slowing the calculation.

```
evaluating expression: 2^54
evaluating power (~17 digits)...
calculating collatz sequence...
step       54  current 1  peak 18014398509481984
```

Use `--progress` to force step updates when stderr is piped, or `--no-progress` to disable.

### Default output

```
steps: 111
peak: 9232
```

### Examples

```powershell
# Step count and peak (default)
.\target\release\collatz.exe 27

# Arithmetic expressions
.\target\release\collatz.exe "2^54"
.\target\release\collatz.exe "12340*248"
.\target\release\collatz.exe "(2+3)^4"

# Step count only
.\target\release\collatz.exe --steps-only 27

# Full sequence plus summary
.\target\release\collatz.exe --show-sequence 27

# Machine-readable output
.\target\release\collatz.exe --json 27
.\target\release\collatz.exe --json --show-sequence 27
```

Invalid input (empty, zero, negative result, non-numeric, division by zero) exits with code `1`.
