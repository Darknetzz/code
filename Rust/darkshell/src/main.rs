mod ast;
mod builtins;
mod expand;
mod interp;
mod lexer;
mod parser;
mod repl;
mod shell;
mod signals;
mod style;

use std::fs;
use std::io::{self, Read, Write};
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::Parser;
use is_terminal::IsTerminal;

#[derive(Parser, Debug)]
#[command(
    name = "dsh",
    version,
    about = "Darkshell (dsh) — cross-platform Bash-like experimental shell"
)]
struct Cli {
    #[arg(short = 'c', long, value_name = "COMMAND")]
    command: Option<String>,

    #[arg(short = 'i', long, help = "Force REPL even when stdin is not a TTY")]
    interactive: bool,

    #[arg(value_name = "SCRIPT_OR_ARGS")]
    script_and_args: Vec<String>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let mut st = shell::ShellState::inherit_from_os();

    signals::install_sigint_handler();

    let stdin = std::io::stdin();
    let stdin_tty = stdin.is_terminal();

    // If argv is only the program name, `dsh .\script.dsh` never reached us (common: a
    // PowerShell `function dsh { ... }` that omits `@args`). Help before we REPL or read stdin.
    if cli.command.is_none() && cli.script_and_args.is_empty() {
        let argc = std::env::args().count();
        if argc <= 1 {
            eprintln!("dsh: note: this process started with no script path on the command line.");
            eprintln!("dsh:       if you ran `dsh .\\script.dsh` but see this, your `dsh` is probably a shell function or alias that does not forward arguments.");
            eprintln!("dsh:       try:  & '.\\target\\release\\dsh.exe' '.\\script.dsh'   (or `cargo run -- .\\script.dsh`)");
            let _ = io::stderr().flush();
        }
    }

    if let Some(code) = cli.command {
        st.argv0 = "dsh".into();
        st.positional.clear();
        interp::eval_source(&mut st, &code)?;
    } else if let Some(path) = cli.script_and_args.first() {
        let path = PathBuf::from(path);
        st.argv0 = path.display().to_string();
        st.positional = cli.script_and_args.iter().skip(1).cloned().collect();
        let contents = fs::read_to_string(&path)
            .with_context(|| format!("reading script `{}`", path.display()))?;
        interp::eval_source_streams(
            &mut st,
            &contents,
            &mut std::io::stdout(),
            &mut std::io::stderr(),
        )?;
    } else if cli.interactive || stdin_tty {
        repl::repl_loop(&mut st)?;
    } else {
        const STDIN_SCRIPT_MAX: u64 = 4 * 1024 * 1024;
        eprintln!(
            "dsh: no script path on the command line; reading a script from standard input (max {} MiB).",
            STDIN_SCRIPT_MAX / 1024 / 1024
        );
        eprintln!(
            "dsh: send EOF when done (Ctrl+Z then Enter in classic CMD), or run e.g.  dsh .\\script.dsh"
        );
        let _ = io::stderr().flush();
        let mut raw = Vec::new();
        stdin
            .lock()
            .take(STDIN_SCRIPT_MAX.saturating_add(1))
            .read_to_end(&mut raw)?;
        if raw.len() as u64 > STDIN_SCRIPT_MAX {
            anyhow::bail!(
                "dsh: standard input exceeds {} MiB; pass a file path instead",
                STDIN_SCRIPT_MAX / 1024 / 1024
            );
        }
        let buf = String::from_utf8(raw).context("dsh: standard input is not valid UTF-8")?;
        interp::eval_source_streams(
            &mut st,
            &buf,
            &mut std::io::stdout(),
            &mut std::io::stderr(),
        )?;
    }

    if let Some(code) = st.pending_exit.take() {
        std::process::exit(code);
    }

    Ok(())
}
