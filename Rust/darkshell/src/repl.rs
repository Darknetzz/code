//! Interactive line editor wrapper.

use std::path::PathBuf;

use anyhow::Result;
use rustyline::completion::{Completer, Pair};
use rustyline::error::ReadlineError;
use rustyline::highlight::Highlighter;
use rustyline::hint::Hinter;
use rustyline::validate::Validator;
use rustyline::{Context, Editor, Helper};
use crate::completion;
use crate::interp::eval_line_streams;
use crate::shell::ShellState;
use crate::signals;
use crate::style;

struct DshHelper {
    state: ShellState,
}

impl DshHelper {
    fn new(state: &ShellState) -> Self {
        Self {
            state: state.clone(),
        }
    }

    fn refresh(&mut self, state: &ShellState) {
        self.state = state.clone();
    }
}

impl Completer for DshHelper {
    type Candidate = Pair;

    fn complete(
        &self,
        line: &str,
        pos: usize,
        _ctx: &Context<'_>,
    ) -> rustyline::Result<(usize, Vec<Pair>)> {
        Ok(completion::completions_at(&self.state, line, pos))
    }
}

impl Helper for DshHelper {}
impl Hinter for DshHelper {
    type Hint = String;
}
impl Highlighter for DshHelper {}
impl Validator for DshHelper {}

pub fn dshrc_path() -> Option<PathBuf> {
    dirs::home_dir().map(|home| home.join(".dshrc"))
}

pub fn history_path() -> Option<PathBuf> {
    dirs::home_dir().map(|home| home.join(".dsh_history"))
}

fn load_dshrc(st: &mut ShellState) {
    let Some(path) = dshrc_path() else {
        return;
    };
    if !path.is_file() {
        return;
    }
    if let Err(e) = crate::interp::eval_source_path(st, &path) {
        let _ = style::writeln_shell_error(&mut std::io::stderr(), &e);
    }
}

pub fn repl_loop(st: &mut ShellState) -> Result<()> {
    signals::install_sigint_handler();
    load_dshrc(st);

    let mut rl = Editor::<DshHelper, _>::with_config(
        rustyline::Config::builder()
            .history_ignore_space(true)
            .build(),
    )?;
    rl.set_helper(Some(DshHelper::new(st)));

    if let Some(path) = history_path() {
        let _ = rl.load_history(&path);
    }

    style::print_repl_banner()?;

    loop {
        if let Some(h) = rl.helper_mut() {
            h.refresh(st);
        }

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
                    if let Some(path) = history_path() {
                        let _ = rl.append_history(&path);
                    }
                    std::process::exit(code);
                }
            }
            Err(ReadlineError::Interrupted) => continue,
            Err(ReadlineError::Eof) => break,
            Err(e) => anyhow::bail!("{e}"),
        }
    }

    if let Some(path) = history_path() {
        let _ = rl.append_history(&path);
    }

    Ok(())
}
