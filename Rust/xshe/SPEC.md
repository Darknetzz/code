# xshe language sketch (v0)

xshe is **Bash-inspired, not Bash-compatible**. This document freezes early semantics enough to implement and test against.

## Lexical syntax

- **Whitespace**: Spaces and tabs separate words. Newlines act like `;` when separating commands inside a `{ ... }` block or script.
- **Comments**: `#` begins a comment; the rest of the line is discarded.
- **Quoting**: `'` ... `'` is literal except that a single quote cannot appear inside (use concatenation `'it'"'"'s'` or double quotes later). `"` ... `"` allows `$`-expansion (`$VAR`, `${VAR}`, `$?`, `$$`, `$1`).
- **Escapes**: Outside quotes, `\` escapes the next character (`\$` emits a literal `$`).

## Redirections (elementary)

| Form | Meaning |
|------|---------|
| `< word` | Open stdin (`fd 0`) from file |
| `> word` | Truncate/create stdout (`fd 1`) |
| `>> word` | Append stdout (`fd 1`) |
| `n> word` | Redirect fd `n` to file (`2> file`, etc.) |
| `n>> word` | Append fd `n` |
| `n>&m` | Duplicate fd `n` to `m` (`2>&1`) |

Redirections may appear before or after the command words; they apply to that simple command in a pipeline.

## Pipelines and lists

- **Pipeline**: `simple | simple | ...` — stdout of each process feeds stdin of the next.
- **List separators**:
  - `;` or newline: always run the next segment.
  - `&&`: run next segment only if the previous exited with status `0`.
  - `||`: run next segment only if the previous exited non-zero.
- `&&` and `||` chain with **equal precedence, left-to-right** (similar to Bash).

## Assignments

- **Prefix assignments** attach only to the **following** external command or builtin invocation:  
  `VAR=value cmd ...` overlays the environment for that command (like Bash).
- `export VAR=value` persists `VAR` in the shell session (exported to children).
- Ordinary variables can be referenced with `$VAR` after export or when set for expansion purposes (see builtins).

## Control flow

- **`if`**  
  ```
  if list; then list; (elif list; then list;)* (else list;)? fi
  ```
  The conditional `list` runs to obtain an exit status: **only the last pipeline** in that list determines success (`0`).
- **`while`**  
  ```
  while list; do list; done
  ```
- **`for`**  
  ```
  for name in words...; do list; done
  ```
  Words are arbitrary expanded words separated by whitespace at parse time (no IFS complexity in v0).
- **Functions**  
  ```
  name() { list; }
  ```
  Positional parameters `$1`… are set for the function body; `$#` is supported.

## Builtins

| Builtin | Behavior |
|---------|----------|
| `cd [dir]` | Change `PWD`; default `HOME` (or user profile on Windows). |
| `export [NAME[=value] ...]` | Set/export variables in the shell environment. |
| `unset NAME ...` | Remove variables. |
| `pwd` | Print working directory. |
| `echo [args...]` | Print arguments separated by spaces, then newline. |
| `exit [n]` | Exit the shell with status `n` (default last status or `0`). |

## Exit status

- Last external command’s wait status is stored (truncated to 8 bits where applicable).
- Missing commands or expansion to empty command name is an error with non-zero status.

## Intentional non-goals (v0)

- Bash parameter expansion beyond `$VAR`, `${VAR}`, `$?`, `$$`, `$n`, `$#`.
- Arrays, `select`, `case`, arithmetic `(( ))`, process substitution, here-documents.
- Job control (`fg`, `bg`, `%1`) or `set -e` — see [WINDOWS.md](WINDOWS.md) for platform notes.
