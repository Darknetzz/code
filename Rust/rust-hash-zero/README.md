# rust-hash-zero

**Canonical implementation** for CPU hash brute-force with leading/trailing zero runs. Replaces the core CPU path of the legacy Python tool in `Python/leadingzeroes/`. Use Python `leadingzeroes` only for OpenCL GPU or recurring-pattern modes not implemented here.

CLI for finding and verifying cryptographic hashes with leading or trailing runs of a hex character.

Brute-forces a nonce over a structured input (`find`) or checks a fixed input (`verify`). Supports SHA-256 and SHA-512. Match any hex digit with `--char`, or use `--unit bits` for zero-bit runs.

## Build

```powershell
cd Rust/rust-hash-zero
cargo build --release
```

Release builds are recommended; the hot path is parallel hashing.

## Usage

```powershell
# Random 12-char hex prefix, input like "a3f2...:0", "a3f2...:1", ...
cargo run --release -- find --zeros 4 --unit hex

# Explicit prefix with colon join (default)
cargo run --release -- find hello --zeros 4 --unit hex

# Old-style plain concatenation
cargo run --release -- find hello --zeros 4 --join concat

cargo run --release -- verify "hello:45231" --zeros 4 --unit hex --json
```

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `find [PREFIX]` | Brute-force `hash(input)` until the match target is met. |
| `verify <INPUT>` | Hash a fixed input and report whether it meets the target. |

### Shared flags

| Flag | Default | Description |
|------|---------|-------------|
| `--zeros <N>` | prompted | Target run length; prompted interactively if omitted. |
| `--side leading\|trailing\|any` | `leading` | Which end to match from; `any` uses whichever end has the longer run. |
| `--char <DIGIT>` | `0` | Hex digit to match, or `any` for any repeated digit. |
| `--unit hex\|bits` | `hex` | Hex = consecutive matching nibbles; bits = consecutive zero bits. |
| `--algorithm sha256\|sha512` | `sha256` | Hash algorithm. |
| `--json` | off | Emit a JSON report. |

With `--unit bits`, only zero bits are supported (`--char` must be `0`; `any` is not allowed).

### `find` flags

| Flag | Default | Description |
|------|---------|-------------|
| `[PREFIX]` | random | Optional prefix string. If omitted, a random hex prefix is generated. |
| `--prefix-len <N>` | `12` | Length of the random hex prefix when PREFIX is omitted. |
| `--join concat\|dash\|colon\|pipe` | `colon` | How prefix and nonce are combined (`prefix:42`, `prefix-42`, etc.). |
| `--nonce-start <N>` | `0` | Starting nonce value. |
| `--nonce-format decimal\|hex` | `decimal` | How the nonce is formatted in the input. |
| `--threads <N>` | all CPUs | Rayon worker thread count. |
| `--progress` | on (unless `--json`) | Show live search progress on stderr. |
| `--no-progress` | | Disable progress output. |
| `--progress-interval <MS>` | `1000` | How often to refresh progress (milliseconds). |

### Input format

Each attempt builds a string from the prefix and nonce:

| `--join` | Example (`prefix=hello`, `nonce=42`) |
|----------|--------------------------------------|
| `colon` (default) | `hello:42` |
| `dash` | `hello-42` |
| `pipe` | `hello\|42` |
| `concat` | `hello42` |

That string is what gets hashed.

### Difficulty

Each additional matching hex character multiplies expected search time by roughly 16×. Each additional zero bit multiplies it by roughly 2×.

### Examples

```powershell
# Random prefix, default colon join
.\target\release\rust-hash-zero.exe find --zeros 4 --unit hex

# Explicit prefix
.\target\release\rust-hash-zero.exe find hello --zeros 4 --unit hex

# 3 trailing 'f' nibbles
.\target\release\rust-hash-zero.exe find test --zeros 3 --char f --side trailing

# 3 repeats of any digit at either end
.\target\release\rust-hash-zero.exe find --zeros 3 --char any --side any

# Legacy plain concatenation
.\target\release\rust-hash-zero.exe find hello --zeros 4 --join concat
```

### Default `find` output

```
prefix: a3f2b1c9d4e8
prefix_random: yes
join: colon
nonce: 10284
input: a3f2b1c9d4e8:10284
hash: 0006bc9ad4253c42...
run: 3 x '0' (specific, leading, hex)
attempts: 10.3K
elapsed_ms: 17
hash_rate: 580K/s
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (`find` found a match; `verify` meets target). |
| `1` | Failure (`verify` does not meet target, or invalid input / runtime error). |
