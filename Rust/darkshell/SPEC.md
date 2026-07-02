# Darkshell language sketch (v0)

**Darkshell** is the project; the installed binary is **`dsh`**. The language is **Bash-inspired, not Bash-compatible**. This document freezes early semantics enough to implement and test against.

## Naming note

The binary name `dsh` matches the common short form for **Darkshell**. Be aware that **another unrelated tool** also uses the name `dsh` on many Linux systems (**Dancer’s / distributed shell** for running commands on multiple hosts). If you install both, pick a non-conflicting install path or rename one of them.

## Lexical syntax

- **Whitespace**: Spaces and tabs separate words. Newlines act like `;` when separating commands inside a `{ ... }` block or script.
- **Comments**: `#` begins a comment; the rest of the line is discarded.
- **Quoting**: `'` ... `'` is literal except that a single quote cannot appear inside (use concatenation `'it'"'"'s'` or double quotes later). `"` ... `"` allows `$`-expansion (`$VAR`, `${VAR}`, `$?`, `$$`, `$1`).
- **Escapes**: Outside quotes, `\` escapes the next character (`\$` emits a literal `$`).
- **Command substitution**: `$(...)` is rejected at lex time (not implemented in v0).

## Redirections (elementary)

| Form | Meaning |
|------|---------|
| `< word` | Open stdin (`fd 0`) from file |
| `> word` | Truncate/create stdout (`fd 1`) |
| `>> word` | Append stdout (`fd 1`) |
| `n> word` | Redirect fd `n` to file (`2> file`, etc.) |
| `n>> word` | Append fd `n` |
| `n>&m` | Duplicate fd `n` to `m` (`2>&1`) |

Redirections may appear before or after the command words; they apply to that simple command (builtins and externals). `2>&1` without an explicit stdout file merges stderr onto stdout.

## Pipelines and lists

- **Pipeline**: `simple | simple | ...` — stdout of each process feeds stdin of the next.
- **List separators**:
  - `;` or newline: always run the next segment.
  - `&&`: run next segment only if the previous exited with status `0`.
  - `||`: run next segment only if the previous exited non-zero.
- `&&` and `||` chain with **equal precedence, left-to-right** (similar to Bash).

## Assignments

- **Prefix assignments** attach only to the **following** command (builtin, function, or external):  
  `VAR=value cmd ...` overlays the environment for that command, including during word expansion (`FOO=bar echo $FOO` → `bar`).
- `export VAR=value` persists `VAR` in the shell session (exported to children).
- Only **exported** variables (plus prefix-overlay keys for that command) are passed to child processes.
- Non-exported shell variables are visible for expansion but are not inherited by externals.

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
  Positional parameters `$1`… are set for the function body; `$#` is supported. `return [n]` exits the function with status `n` (default last status). `exit` exits the entire shell.

## Builtins

| Builtin | Behavior |
|---------|----------|
| `cd [dir]` | Change `PWD`; default `HOME` (or user profile on Windows). |
| `export [NAME[=value] ...]` | Set/export variables in the shell environment. |
| `unset NAME ...` | Remove variables. |
| `pwd` | Print working directory. |
| `echo [args...]` | Print arguments separated by spaces, then newline. |
| `help [topic]` | Print dsh usage (not Windows `help`); optional `topic` is a builtin name. |
| `exit [n]` | Exit the shell with status `n` (default last status or `0`). |
| `return [n]` | Return from the current function with status `n` (invalid at top level). |
| `source file` / `. file` | Execute `file` in the current shell environment. |
| `type name` | Report whether `name` is a builtin, function, or external command. |
| `true` / `false` / `:` | Exit status 0, 1, or no-op success. |

## Exit status

- Last command’s status is stored (builtins and functions included; truncated to 8 bits where applicable).
- Missing commands or expansion to empty command name is an error with non-zero status.

## Intentional non-goals (v0)

- Bash parameter expansion beyond `$VAR`, `${VAR}`, `$?`, `$$`, `$n`, `$#`.
- Command substitution (`$(...)`, backticks).
- Arrays, `select`, `case`, arithmetic `(( ))`, process substitution, here-documents.
- Job control (`fg`, `bg`, `%1`) or `set -e` — see [WINDOWS.md](WINDOWS.md) for platform notes.
