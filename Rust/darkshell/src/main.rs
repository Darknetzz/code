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
use std::io::{self, Write};
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

    /// Accepted for compatibility; without a script path the REPL always starts.
    #[arg(short = 'i', long, hide = true)]
    interactive: bool,

    #[arg(value_name = "SCRIPT_OR_ARGS")]
    script_and_args: Vec<String>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let _ = cli.interactive;
    let mut st = shell::ShellState::inherit_from_os();

    signals::install_sigint_handler();

    // If argv is only the program name, `dsh .\script.dsh` never reached us (common: a
    // PowerShell `function dsh { ... }` that omits `@args`).
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
    } else if let Some(path_str) = cli.script_and_args.first() {
        let path = PathBuf::from(path_str);
        if !path.is_file() {
            anyhow::bail!(
                "dsh: script file does not exist or is not a regular file: {}",
                path.display()
            );
        }
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
    } else {
        // Embedded / IDE terminals often leave stdin as a pipe. Rustyline then blocks forever on
        // the first read with no useful prompt — looks like a freeze. Require a real TTY stdin.
        if !std::io::stdin().is_terminal() {
            eprintln!("dsh: cannot start the interactive shell: standard input is not a terminal.");
            eprintln!("dsh: run a script by passing a file path to this executable, for example:");
            eprintln!("dsh:   .\\target\\release\\dsh.exe .\\script.dsh");
            eprintln!("dsh: or:  cargo run -- .\\script.dsh");
            eprintln!("dsh: if you already used a path but see this message, the path was not passed to this process (often a PowerShell function named `dsh` without `@args`).");
            let _ = io::stderr().flush();
            std::process::exit(1);
        }
        repl::repl_loop(&mut st)?;
    }

    if let Some(code) = st.pending_exit.take() {
        std::process::exit(code);
    }

    Ok(())
}
