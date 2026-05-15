//! ANSI styling for interactive TTY output.

use std::io::{self, Write};
use std::path::Path;

use is_terminal::IsTerminal;
use owo_colors::OwoColorize;

fn stdout_color() -> bool {
    io::stdout().is_terminal()
}

fn stderr_color() -> bool {
    io::stderr().is_terminal()
}

pub fn print_repl_banner() -> io::Result<()> {
    let mut out = io::stdout().lock();
    if stdout_color() {
        writeln!(
            out,
            "{} {}",
            "Darkshell".bold().bright_cyan(),
            "(dsh)".bright_blue()
        )?;
        writeln!(
            out,
            "{}",
            "Use exit to quit; Ctrl+D to exit.".bright_yellow()
        )?;
    } else {
        writeln!(
            out,
            "Darkshell (dsh). Use exit to quit; Ctrl+D to exit."
        )?;
    }
    Ok(())
}

/// `(raw, styled)` for [`rustyline`](https://docs.rs/rustyline/latest/rustyline/prompt/trait.Prompt.html):
/// width is derived from `raw` (no ANSI); the terminal shows `styled` when colors are on.
pub fn repl_prompt_pair(cwd: &Path) -> (String, String) {
    let path = cwd.to_string_lossy();
    let raw = format!("dsh:{path}$ ");
    let styled = if stdout_color() {
        format!(
            "{}{}{} ",
            "dsh:".bold().bright_magenta(),
            path.as_ref().bright_cyan(),
            "$".bold().bright_green(),
        )
    } else {
        raw.clone()
    };
    (raw, styled)
}

pub fn writeln_shell_error(mut w: impl Write, err: &impl std::fmt::Display) -> io::Result<()> {
    let msg = format!("{err}");
    if stderr_color() {
        writeln!(w, "{}", msg.bright_red())?;
    } else {
        writeln!(w, "{msg}")?;
    }
    Ok(())
}
