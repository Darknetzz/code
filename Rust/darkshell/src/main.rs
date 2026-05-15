mod ast;
mod builtins;
mod expand;
mod interp;
mod lexer;
mod parser;
mod repl;
mod shell;
mod signals;

use std::fs;
use std::io::Read;
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
        let mut buf = String::new();
        stdin.lock().read_to_string(&mut buf)?;
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
