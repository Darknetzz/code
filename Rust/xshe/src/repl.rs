//! Interactive line editor wrapper.

use anyhow::Result;
use rustyline::error::ReadlineError;
use rustyline::DefaultEditor;

use crate::interp::eval_line_streams;
use crate::shell::ShellState;
use crate::signals;

pub fn repl_loop(st: &mut ShellState) -> Result<()> {
    signals::install_sigint_handler();
    let mut rl = DefaultEditor::new()?;
    println!("xshe interactive mode. Use exit to quit; Ctrl+D to exit.");

    loop {
        let prompt = format!("xshe:{}$ ", st.cwd.display());
        match rl.readline(&prompt) {
            Ok(line) => {
                rl.add_history_entry(line.as_str())?;
                eval_line_streams(st, &line, &mut std::io::stdout(), &mut std::io::stderr())?;

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
