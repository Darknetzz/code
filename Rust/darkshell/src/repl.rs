//! Interactive line editor wrapper.

use std::path::{Path, PathBuf};

use anyhow::Result;
use rustyline::completion::{Completer, Pair};
use rustyline::error::ReadlineError;
use rustyline::highlight::Highlighter;
use rustyline::hint::Hinter;
use rustyline::validate::Validator;
use rustyline::{Context, Editor, Helper};
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
        let prefix = &line[..pos];
        let start = prefix
            .rfind(|c: char| c.is_whitespace())
            .map(|i| i + 1)
            .unwrap_or(0);
        let word = &line[start..pos];
        if word.is_empty() {
            return Ok((start, Vec::new()));
        }

        let mut candidates: Vec<Pair> = Vec::new();

        for name in builtin_names() {
            if name.starts_with(word) {
                candidates.push(Pair {
                    display: name.to_string(),
                    replacement: name.to_string(),
                });
            }
        }

        let mut fnames: Vec<_> = self.state.functions.keys().map(String::as_str).collect();
        fnames.sort();
        for name in fnames {
            if name.starts_with(word) {
                candidates.push(Pair {
                    display: name.to_string(),
                    replacement: name.to_string(),
                });
            }
        }

        if word.starts_with('$') {
            let var_prefix = &word[1..];
            let mut keys: Vec<_> = self.state.env.keys().map(String::as_str).collect();
            keys.sort();
            for key in keys {
                if key.starts_with(var_prefix) {
                    candidates.push(Pair {
                        display: format!("${key}"),
                        replacement: format!("${key}"),
                    });
                }
            }
        } else if start == 0 {
            let dir = if word.contains('\\') || word.contains('/') {
                let parent = Path::new(word)
                    .parent()
                    .filter(|p| !p.as_os_str().is_empty())
                    .unwrap_or_else(|| Path::new("."));
                let base = Path::new(word)
                    .file_name()
                    .and_then(|s| s.to_str())
                    .unwrap_or(word);
                (parent.to_path_buf(), base)
            } else {
                (self.state.cwd.clone(), word)
            };
            if let Ok(entries) = std::fs::read_dir(&dir.0) {
                for entry in entries.flatten() {
                    let name = entry.file_name().to_string_lossy().into_owned();
                    if name.starts_with(&dir.1) {
                        let mut replacement = if start == 0 && dir.0 == self.state.cwd {
                            name.clone()
                        } else {
                            let parent = Path::new(word).parent().unwrap_or(Path::new("."));
                            parent.join(&name).to_string_lossy().into_owned()
                        };
                        if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                            replacement.push(std::path::MAIN_SEPARATOR);
                        }
                        candidates.push(Pair {
                            display: name,
                            replacement,
                        });
                    }
                }
            }
        }

        candidates.sort_by(|a, b| a.display.cmp(&b.display));
        candidates.dedup_by(|a, b| a.replacement == b.replacement);
        Ok((start, candidates))
    }
}

impl Helper for DshHelper {}
impl Hinter for DshHelper {
    type Hint = String;
}
impl Highlighter for DshHelper {}
impl Validator for DshHelper {}

fn builtin_names() -> &'static [&'static str] {
    &[
        "cd", "export", "unset", "pwd", "echo", "exit", "return", "help", "source", ".", "type",
        ":", "true", "false",
    ]
}

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
