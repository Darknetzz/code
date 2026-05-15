# Darkshell (`dsh`)

**Darkshell** is an experimental, **Bash-inspired** shell implemented in Rust. The shipped binary is **`dsh`**. It runs on **Windows, Linux, and macOS**, with behavior documented for both Unix-style and Windows consoles.

> **Status:** early / v0. The language is **not** Bash-compatible. Use it to learn, hack on, or drive simple scripts—not as a full replacement for your daily shell yet.

---

## Table of contents

- [Why Darkshell?](#why-darkshell)
- [Naming: `dsh` vs other tools](#naming-dsh-vs-other-tools)
- [Features (current)](#features-current)
- [Non-goals and limitations](#non-goals-and-limitations)
- [Build and install](#build-and-install)
- [Running `dsh`](#running-dsh)
- [Interactive REPL](#interactive-repl)
- [Language overview](#language-overview)
  - [Lexical rules](#lexical-rules)
  - [Lists, conditionals, pipelines](#lists-conditionals-pipelines)
  - [Redirections](#redirections)
  - [Environment and assignments](#environment-and-assignments)
  - [Control flow](#control-flow)
  - [Functions](#functions)
  - [Expansion](#expansion)
- [Builtins](#builtins)
- [Exit status](#exit-status)
- [Windows vs Unix](#windows-vs-unix)
- [Repository layout](#repository-layout)
- [Testing](#testing)
- [Further reading](#further-reading)
- [License](#license)

---

## Why Darkshell?

- **Small, readable codebase** in Rust (lexer, parser, AST, interpreter).
- **Cross-platform** `cd`, `pwd`, paths, and subprocess spawning without relying on a POSIX-only layer for core features.
- **Familiar surface syntax** for anyone who knows Bash: `if` / `while` / `for`, `&&` / `||`, pipes, `export`, here-style comments, etc.—where implemented.

---

## Naming: `dsh` vs other tools

The binary name **`dsh`** is the short form for **Darkshell**.

On many **Linux** systems, a **different** program also called `dsh` exists (**Dancer’s Shell** / distributed shell for remote clusters). If you install both, use distinct paths or rename one binary to avoid clashes.

---

## Features (current)

| Area | What works |
|------|------------|
| **Invocation** | REPL (no args), `dsh -c '…'`, script file + args (first arg must be an existing file) |
| **Line editing** | [rustyline](https://github.com/kkawakam/rustyline)-based interactive prompt (TTY-aware styling on supported terminals) |
| **Commands** | External programs via `std::process::Command`, builtins, user-defined functions |
| **Composition** | `;`, `&&`, `||`, `|` pipelines (with restrictions, see below) |
| **Redirects** | `<`, `>`, `>>`, `n>`, `n>>`, `2>&1`-style dup where implemented |
| **Variables** | `export`, `unset`, prefix `VAR=value cmd`, `$VAR`, `${VAR}`, `$?`, `$$`, `$1`…, `$#` |
| **Control flow** | `if` / `then` / `elif` / `else` / `fi`, `while` / `do` / `done`, `for` / `in` / `do` / `done` |
| **Functions** | `name() { … }` with positional parameters in the body |
| **Misc** | `#` comments, `&` background (best-effort), `help` builtin (dsh help—not Windows CMD `help`) |

Authoritative semantics for the language **v0** are in [`SPEC.md`](SPEC.md).

---

## Non-goals and limitations

These are **intentionally** out of scope or incomplete in v0 (see [`SPEC.md`](SPEC.md)):

- Full Bash **parameter expansion** (only a small `$…` subset).
- **Arrays**, `select`, `case`, arithmetic `(( ))`, process substitution, here-documents.
- **Job control** (`fg`, `bg`, `%1`) and **`set -e`**.
- **Pipelines:** multi-command pipelines **cannot** mix builtins (builtins are not supported inside `|` chains). Redirects and prefix assignments on pipeline segments are **not** supported yet for multi-command pipes.
- **Background `&`:** runs in a detached way; do not expect POSIX job-control semantics (especially on Windows—see [`WINDOWS.md`](WINDOWS.md)).

---

## Build and install

**Requirements:** Rust toolchain (**2021 edition**), e.g. stable via [rustup](https://rustup.rs/).

```bash
cd Rust/darkshell   # or your clone path
cargo build --release
```

The binary is `target/release/dsh` (or `target\release\dsh.exe` on Windows). Add that directory to your `PATH`, or copy the binary where you prefer.

```bash
cargo install --path .
```

installs `dsh` from the crate manifest into Cargo’s bin directory (if you use this workflow).

---

## Running `dsh`

| Mode | Example |
|------|---------|
| **Interactive REPL** | `dsh` with no script path (always starts the REPL; does not read stdin as a script) |
| **One command** | `dsh -c "echo hello"` |
| **Script file** | `dsh script.dsh arg1 arg2` — first arg must exist as a regular file; `$0` is the script path, `$1`… are args |

CLI flags (from `dsh --help`):

- **`-c COMMAND` / `--command COMMAND`** — run `COMMAND` and exit (after `exit` handling).
- **Positional args** — first arg is a script path; remaining args become `$1`, `$2`, … If the path is missing or not a regular file, `dsh` prints an error and exits.

---

## Interactive REPL

- On a color-capable **TTY**, the banner and prompt use ANSI styling; **plain** output is used when stdout/stderr are redirected so scripts stay clean.
- The prompt shows the current working directory (see `PWD` / `cd`).
- **Leave the shell:** run the **`exit`** builtin, or press **Ctrl+D** (end-of-input) at the prompt.
- Parse/runtime errors print to **stderr** and the REPL **continues** (you are not dropped back to the OS on the first typo).

---

## Language overview

### Lexical rules

- **Whitespace:** spaces and tabs separate words. Inside `{ … }` blocks or scripts, **newlines** can separate commands like `;`.
- **Comments:** `#` starts a comment; the rest of the line is ignored.
- **Single quotes** `'…'` — literal; a single `'` cannot appear inside (use concatenation or double quotes).
- **Double quotes** `"…"` — allow **$** expansion (`$VAR`, `${VAR}`, `$?`, etc.).
- **Escapes:** outside quotes, `\` escapes the next character (e.g. `\$` → literal `$`).
- **Line endings:** scripts may use `\n` or `\r\n`; `\r` is treated as whitespace.

### Lists, conditionals, pipelines

- **`;`** or newline (in blocks): always run the next segment.
- **`&&`:** run the next segment only if the previous exited with status **0**.
- **`||`:** run the next segment only if the previous exited **non-zero**.
- **`&&` and `||`** have **equal precedence, left-to-right** (similar to Bash).
- **`|`** connects simple commands: stdout of one process feeds stdin of the next.

**Pipeline restrictions (v0):**

- Only **external** commands in multi-stage pipes (no builtins in the middle/end of a pipe chain).
- No redirects or prefix `VAR=value` assignments on individual commands inside a **multi-command** pipeline yet.

### Redirections

| Form | Meaning |
|------|---------|
| `< word` | stdin (fd `0`) from file |
| `> word` | stdout (fd `1`) truncate/create |
| `>> word` | stdout append |
| `n> word` | redirect fd `n` to file (e.g. `2> err.log`) |
| `n>> word` | append fd `n` |
| `n>&m` | duplicate fd `n` to `m` (e.g. `2>&1`) |

Redirects may appear **before or after** the command words on a **simple** command; they apply to that command in the pipeline.

### Environment and assignments

- **`export NAME=value`** — sets and exports variables for the shell and child processes.
- **`export NAME`** — marks `NAME` as exported (value comes from the shell if already set).
- **`export`** with no arguments — lists exported variables in a shell-friendly form.
- **`VAR=value command …`** — sets `VAR` in the environment **only for that command** (overlay), like Bash.

### Control flow

**`if`** (condition is a **list**; **last** pipeline’s status decides truth):

```bash
if true; then echo yes; fi
if test -f foo; then echo exists; else echo missing; fi
```

**`while`:**

```bash
while false; do echo never; done
```

**`for`:**

```bash
for x in a b c; do echo "$x"; done
```

Words after `in` are parsed as words and expanded—no `IFS` splitting complexity in v0.

### Functions

```bash
greet() { echo "hello $1"; }
greet world
```

`$1`, `$2`, … and `$#` are available in the function body.

### Expansion

Supported forms include **`$VAR`**, **`${VAR}`**, **`$?`** (last status), **`$$`**, positional **`$n`**, and **`$#`**. Beyond that, see [`SPEC.md`](SPEC.md) for what is explicitly *not* implemented.

---

## Builtins

| Builtin | Summary |
|---------|---------|
| **`help`** `[topic]` | Darkshell help. On Windows, plain `help` would run CMD’s `help.exe`; **`help` is a builtin** so you always get dsh documentation. Use `cmd /c help` for CMD. |
| **`cd`** `[dir]` | Change directory; default **home** (`HOME` or on Windows `USERPROFILE` / dirs fallback). Updates `PWD`. |
| **`pwd`** | Print current working directory. |
| **`echo`** `words…` | Print arguments separated by spaces, then newline. |
| **`export`** | Set/export variables, or list exports when given no args. |
| **`unset`** `names…` | Remove shell variables. |
| **`exit`** `[n]` | Exit the shell with status `n` (default: last command status). |
| **`:`**, **`true`**, **`false`** | No-op success, success (`0`), failure (`1`). |

Run **`help`** or **`help cd`** inside `dsh` for the full builtin text.

---

## Exit status

- The last **external** command’s wait status is remembered (as **`$?`**), truncated to 8 bits where the OS applies that.
- **Missing** commands or expansion to an **empty** command name yield a **non-zero** status / error.

---

## Windows vs Unix

- **`cd` / `pwd`:** use Rust’s `std::env` APIs; paths follow the OS.
- **Ctrl+C:** Unix targets forward interrupts to a child process group where possible; Windows uses best-effort console handling. Details: [`WINDOWS.md`](WINDOWS.md).
- **Job control / background:** not POSIX job control; background `&` is best-effort—see that doc before relying on it.

---

## Repository layout

| Path | Role |
|------|------|
| `src/main.rs` | CLI entry (`clap`), mode selection (REPL / `-c` / script file) |
| `src/lexer.rs`, `parser.rs`, `ast.rs` | Front-end |
| `src/expand.rs` | Word / parameter expansion |
| `src/interp.rs` | Evaluation: pipelines, builtins, functions, redirects |
| `src/builtins.rs` | Builtin implementations and `help` text |
| `src/repl.rs` | Interactive loop (`rustyline`) |
| `src/shell.rs` | Process-wide state: env, cwd, functions, `exit` |
| `src/signals.rs` | Interrupt / child tracking (platform-specific pieces) |
| `src/style.rs` | TTY-aware banner, prompt, and error styling |
| `tests/integration.rs` | Smoke tests via `assert_cmd` |
| `SPEC.md` | Language semantics (v0) |
| `WINDOWS.md` | Windows-specific behavior notes |

---

## Testing

```bash
cargo test
```

Integration tests spawn the `dsh` binary and assert on stdout/stderr and exit codes.

---

## Further reading

- **[`SPEC.md`](SPEC.md)** — formal v0 language sketch (what the parser and runtime aim to implement).
- **[`WINDOWS.md`](WINDOWS.md)** — signals, job/background notes, paths, line endings.

---

## License

Dual-licensed under **MIT OR Apache-2.0**, as specified in [`Cargo.toml`](Cargo.toml) (`license = "MIT OR Apache-2.0"`).

---

## Contributing

Issues and PRs are welcome. When changing behavior, update **`SPEC.md`** (if semantics change) and any affected tests. Keep **`help`** output in sync with new builtins so Windows users are not surprised by stale text.
