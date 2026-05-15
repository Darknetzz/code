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
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::Parser;
use is_terminal::IsTerminal;

#[derive(Parser, Debug)]
#[command(name = "xshe", version, about = "Cross-platform Bash-like experimental shell")]
struct Cli {
    #[arg(short = 'c', long, value_name = "COMMAND")]
    command: Option<String>,

    #[arg(short = 'i', long, help = "Force REPL even when stdin is redirected")]
    interactive: bool,

    #[arg(value_name = "SCRIPT")]
    script_and_args: Vec<String>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let mut st = shell::ShellState::inherit_from_os();

    signals::install_sigint_handler();

    match (
        cli.command.clone(),
        cli.script_and_args.first(),
        cli.interactive,
    ) {
        (Some(code), _, _) => {
            st.argv0 = PathBuf::from(if cfg!(unix) { "xshe" } else { "xshe.exe" }).display().to_string();
            st.positional.clear();
            interp::eval_source(&mut st, &code)?;
        }
        (None, Some(script), _) => {
            let path = PathBuf::from(script);
            st.argv0 = path.display().to_string();
            st.positional = cli
                .script_and_args
                .iter()
                .skip(1)
                .cloned()
                .collect();
            let contents = fs::read_to_string(&path).with_context(|| script.to_string())?;
            interp::eval_source_streams(
                &mut st,
                &contents,
                &mut std::io::stdout(),
                &mut std::io::stderr(),
            )?;
        }
        (None, None, _) => {
            let stdin = std::io::stdin();
            if cli.interactive || stdin.is_terminal() {
                repl::repl_loop(&mut st)?;
            } else {
                let mut buf = String::new();
                std::io::Read::read_to_string(&mut stdin.lock(), &mut buf)?;
                interp::eval_source_streams(
                    &mut st,
                    &buf,
                    &mut std::io::stdout(),
                    &mut std::io::stderr(),
                )?;
            }
        }
    }

    if let Some(code) = st.pending_exit.take() {
        std::process::exit(code);
    }

    Ok(())
}

