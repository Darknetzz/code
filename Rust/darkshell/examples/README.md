# Darkshell example scripts

Small `.dsh` scripts that demonstrate language features. Run from the **crate root** (`Rust/darkshell/`) unless noted.

```powershell
# Windows (PowerShell) — forward args if `dsh` is a function
cargo run --release -- .\examples\hello.dsh
.\target\release\dsh.exe .\examples\hello.dsh

# Unix
cargo run --release -- ./examples/hello.dsh
./target/release/dsh ./examples/hello.dsh
```

| Script | Topics |
|--------|--------|
| [`hello.dsh`](hello.dsh) | `echo`, `pwd`, `export`, quoting |
| [`control-flow.dsh`](control-flow.dsh) | `if` / `elif` / `else`, `&&` / `||`, `for`, `while` |
| [`functions.dsh`](functions.dsh) | `name() { … }`, `$1`, `return`, `$?` |
| [`environment.dsh`](environment.dsh) | `export`, `unset`, prefix `VAR=val cmd`, child env |
| [`redirects.dsh`](redirects.dsh) | Builtin redirects `>`, `>>`, `2>` |
| [`script-args.dsh`](script-args.dsh) | `$0`, `$1`…, `$#` (pass extra args on the command line) |
| [`builtins.dsh`](builtins.dsh) | `type`, `help`, `true` / `false` |
| [`source/run.dsh`](source/run.dsh) | `source` / `.` — run another file in the current shell |

**Tips**

- Use **`;`** between top-level commands in scripts (especially after `}` closing a function body, and before another `name()` line).
- Builtins (`echo`, etc.) cannot appear inside `|` pipelines; use external commands (e.g. `cmd /c echo` on Windows, `/bin/echo` on Unix).
- `$(command)` is not supported in v0 — the shell reports a parse error.
- [`redirects.dsh`](redirects.dsh) writes `examples/redirects-out.txt` and `examples/redirects-err.txt` (safe to delete).
