//! Interactive line editor wrapper.

use anyhow::Result;
use rustyline::error::ReadlineError;
use rustyline::DefaultEditor;

use crate::interp::eval_line_streams;
use crate::shell::ShellState;
use crate::signals;
use crate::style;

pub fn repl_loop(st: &mut ShellState) -> Result<()> {
    signals::install_sigint_handler();
    let mut rl = DefaultEditor::new()?;
    style::print_repl_banner()?;

    loop {
        let prompt = style::repl_prompt_pair(&st.argv0, st.cwd.as_path());
        match rl.readline(&prompt) {
            Ok(line) => {
                rl.add_history_entry(line.as_str())?;
                if let Err(e) =
                    eval_line_streams(st, &line, &mut std::io::stdout(), &mut std::io::stderr())
                {
                    style::writeln_shell_error(&mut std::io::stderr(), &e)?;
                }

                if let Some(code) = st.pending_exit.take() {
                    std::process::exit(code);
                }
            }
            Err(ReadlineError::Interrupted) => continue,
            Err(ReadlineError::Eof) => break,
            Err(e) => anyhow::bail!("{e}"),
        }
    }

    Ok(())
}
