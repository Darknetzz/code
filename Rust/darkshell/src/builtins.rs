use crate::ast::Word;
use crate::expand::expand_word;
use crate::shell::ShellState;
use anyhow::{bail, Result};
use std::io::Write;
use std::path::PathBuf;

#[derive(Debug, Clone)]
pub enum BuiltinOutcome {
    Status(i32),
    Exit(i32),
    Return(i32),
    Source(PathBuf),
}

pub const BUILTIN_NAMES: &[&str] = &[
    "cd", "export", "unset", "pwd", "echo", "exit", "return", "help", "source", ".", "type", ":",
    "true", "false",
];

pub fn is_builtin(name: &str) -> bool {
    BUILTIN_NAMES.contains(&name)
}

pub fn run_builtin(
    st: &mut ShellState,
    name: &str,
    args: &[Word],
    mut out: impl Write,
) -> Result<BuiltinOutcome> {
    let argv: Vec<String> = args
        .iter()
        .map(|w| expand_word(st, w))
        .collect::<Result<_>>()?;

    match name {
        ":" => Ok(BuiltinOutcome::Status(0)),
        "true" => Ok(BuiltinOutcome::Status(0)),
        "false" => Ok(BuiltinOutcome::Status(1)),
        "exit" => {
            let code = argv
                .first()
                .map(|s| s.parse::<i32>())
                .transpose()?
                .unwrap_or(st.last_status);
            Ok(BuiltinOutcome::Exit(code))
        }
        "return" => {
            if st.function_depth == 0 {
                bail!("return: can only be used in a function");
            }
            let code = argv
                .first()
                .map(|s| s.parse::<i32>())
                .transpose()?
                .unwrap_or(st.last_status);
            Ok(BuiltinOutcome::Return(code))
        }
        "source" | "." => {
            let path = argv
                .first()
                .ok_or_else(|| anyhow::anyhow!("{name}: missing file operand"))?;
            if argv.len() > 1 {
                bail!("{name}: too many arguments");
            }
            Ok(BuiltinOutcome::Source(PathBuf::from(path)))
        }
        "type" => type_cmd(st, &argv, &mut out),
        "pwd" => {
            if !argv.is_empty() {
                bail!("pwd: too many arguments");
            }
            writeln!(out, "{}", st.cwd.display())?;
            Ok(BuiltinOutcome::Status(0))
        }
        "echo" => {
            writeln!(out, "{}", argv.join(" "))?;
            Ok(BuiltinOutcome::Status(0))
        }
        "cd" => cd(st, &argv),
        "export" => export(st, &argv, &mut out),
        "unset" => unset(st, &argv),
        "help" => help(&argv, &mut out),
        other => bail!("unknown builtin `{other}`"),
    }
}

fn cd(st: &mut ShellState, argv: &[String]) -> Result<BuiltinOutcome> {
    let target = match argv.len() {
        0 => crate::shell::home_dir(),
        1 if argv[0] == "-" => st
            .prev_cwd
            .clone()
            .ok_or_else(|| anyhow::anyhow!("cd: OLDPWD not set"))?,
        1 => PathBuf::from(&argv[0]),
        _ => bail!("cd: too many arguments"),
    };

    let abs = if target.is_absolute() {
        target
    } else {
        st.cwd.join(&target)
    };
    let dest = std::fs::canonicalize(&abs)
        .map_err(|e| anyhow::anyhow!("cd: `{}`: {e}", abs.display()))?;

    let old = st.cwd.clone();
    std::env::set_current_dir(&dest)?;
    let fresh = std::env::current_dir().unwrap_or_else(|_| dest.clone());
    st.prev_cwd = Some(old.clone());
    st.cwd = fresh;
    let ps = st.cwd.to_string_lossy().into_owned();
    st.env.insert("PWD".into(), ps);
    st.export_name("PWD");
    st.env
        .insert("OLDPWD".into(), old.to_string_lossy().into_owned());
    st.export_name("OLDPWD");

    Ok(BuiltinOutcome::Status(0))
}

fn export<W: Write>(st: &mut ShellState, argv: &[String], out: &mut W) -> Result<BuiltinOutcome> {
    if argv.is_empty() {
        let keys: Vec<String> = st.exported_keys().into_iter().map(str::to_string).collect();
        for k in keys {
            let v = st.env.get(&k).cloned().unwrap_or_default();
            writeln!(out, "export {}={}", k, sh_quote_value(&v))?;
        }
        return Ok(BuiltinOutcome::Status(0));
    }
    for tok in argv {
        if let Some((k, v)) = tok.split_once('=') {
            st.set_and_export(k.to_string(), v.to_string());
        } else {
            st.export_name(tok);
        }
    }
    Ok(BuiltinOutcome::Status(0))
}

fn help(argv: &[String], out: &mut impl Write) -> Result<BuiltinOutcome> {
    match argv.len() {
        0 => writeln!(out, "{HELP_OVERVIEW}")?,
        1 => {
            let topic = &argv[0];
            if let Some(body) = help_topic(topic) {
                write!(out, "{body}")?;
            } else {
                bail!("help: no help for `{topic}` (try `help` for a list)");
            }
        }
        _ => bail!("help: too many arguments"),
    }
    Ok(BuiltinOutcome::Status(0))
}

const HELP_OVERVIEW: &str = "\
Darkshell (dsh) — experimental bash-like shell. This is `help` for dsh, not Windows CMD.

Builtins:
  help [TOPIC]     Show this overview or one-line help for TOPIC.
  cd [DIR]         Change directory; default is your home/profile directory; `cd -` goes to OLDPWD.
  pwd              Print the current directory.
  echo WORDS...    Print words separated by spaces, then a newline.
  export [N=V...]  Set variables and mark them exported; with no args, list exports.
  unset NAME...    Remove shell variables.
  exit [N]         Leave the shell with status N (default: last command status).
  return [N]       Return from the current function with status N.
  source FILE      Run commands from FILE in the current shell.
  . FILE           Same as source.
  type NAME        Show whether NAME is a builtin, function, or external command.
  true / false     Exit with status 0 or 1.
  :                No-op, status 0.

Syntax highlights:
  a && b / a || b  Run b depending on a’s exit status; ; runs the next command always.
  a | b            Pipeline (stdout of a to stdin of b).
  VAR=value cmd    Set VAR for that command only.
  # text           Rest of line is a comment.

For Windows CMD help (SET, PATH, …), run e.g.  cmd /c help  or  where help
";

fn help_topic(name: &str) -> Option<&'static str> {
    Some(match name {
        "help" => "help [TOPIC] — show dsh help; TOPIC is a builtin name.\n",
        "cd" => "cd [DIR] — change directory; DIR defaults to home; `cd -` returns to OLDPWD.\n",
        "pwd" => "pwd — print working directory; no arguments.\n",
        "echo" => "echo [WORD ...] — print arguments, newline at end.\n",
        "export" => "export [NAME[=VALUE] ...] — set/export vars; no args lists exports.\n",
        "unset" => "unset NAME ... — remove variables from the shell.\n",
        "exit" => "exit [N] — exit dsh with status N (0–255 typical).\n",
        "return" => "return [N] — return from a function with status N.\n",
        "source" | "." => "source FILE / . FILE — run FILE in the current shell.\n",
        "type" => "type NAME — show how NAME would be resolved.\n",
        "true" | "false" => "true / false — exit 0 or 1.\n",
        ":" => ": — no-op, always succeeds.\n",
        _ => return None,
    })
}

fn unset(st: &mut ShellState, argv: &[String]) -> Result<BuiltinOutcome> {
    if argv.is_empty() {
        bail!("unset: missing operand");
    }
    for k in argv {
        st.unset(k.as_str());
    }
    Ok(BuiltinOutcome::Status(0))
}

fn type_cmd(st: &ShellState, argv: &[String], out: &mut impl Write) -> Result<BuiltinOutcome> {
    if argv.len() != 1 {
        bail!("type: expected one NAME");
    }
    let name = &argv[0];
    if is_builtin(name) {
        writeln!(out, "{name} is a shell builtin")?;
    } else if st.functions.contains_key(name) {
        writeln!(out, "{name} is a function")?;
    } else {
        writeln!(out, "{name} is an external command")?;
    }
    Ok(BuiltinOutcome::Status(0))
}

fn sh_quote_value(s: &str) -> String {
    if s.contains(['\'', '\n']) {
        return format!("{}", s.escape_default());
    }
    format!("'{}'", s.replace('\'', r"'\''"))
}
