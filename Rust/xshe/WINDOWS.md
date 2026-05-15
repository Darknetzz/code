# xshe on Windows vs Unix

## Signals and interrupts

- **Unix / Linux**: When running an external command, xshe installs a `Ctrl+C` handler that requests the running child process group to terminate. At the interactive prompt, `rustyline` handles line editing; interrupt during prompt cancels the current line.
- **Windows**: Console control events (`Ctrl+C`) are best-effort. Child processes are terminated without full Unix-style process-group semantics. Interactive line editing uses the same `rustyline` backend; behavior may differ slightly depending on the terminal (Windows Terminal, ConPTY, legacy console).

## Job control

- Bash-style job control (`Ctrl+Z`, `fg`, `bg`, `%` job ids) is **not implemented** on any platform in v0. Background `&` starts a detached child on the best-effort basis; do not rely on POSIX job control semantics on Windows.

## Paths and builtins

- `cd` and `pwd` use Rust’s `std::env::{set_current_dir, current_dir}` and normalize paths per the OS.
- `HOME` is used when available; on Windows, `USERPROFILE` is accepted as a fallback for `cd` with no arguments.

## Line endings

- Scripts may use `\n` or `\r\n`; the lexer treats `\r` as whitespace.
