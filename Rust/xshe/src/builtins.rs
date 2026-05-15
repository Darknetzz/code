use crate::ast::Word;
use crate::expand::expand_word;
use crate::shell::ShellState;
use anyhow::{bail, Result};
use std::io::Write;
use std::path::PathBuf;

#[derive(Debug, Clone, Copy)]
pub enum BuiltinOutcome {
    Status(i32),
    Exit(i32),
}

pub fn is_builtin(name: &str) -> bool {
    matches!(
        name,
        "cd" | "export" | "unset" | "pwd" | "echo" | "exit" | ":" | "true" | "false"
    )
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
        other => bail!("unknown builtin `{other}`"),
    }
}

fn cd(st: &mut ShellState, argv: &[String]) -> Result<BuiltinOutcome> {
    let target = match argv.len() {
        0 => home_dir_fallback(),
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

    std::env::set_current_dir(&dest)?;
    let fresh = std::env::current_dir().unwrap_or_else(|_| dest.clone());
    st.cwd = fresh;
    let ps = st.cwd.to_string_lossy().into_owned();
    st.env.insert("PWD".into(), ps);
    st.export_name("PWD");

    Ok(BuiltinOutcome::Status(0))
}

fn home_dir_fallback() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .ok()
        .or_else(|| std::env::var("USERPROFILE").ok().map(PathBuf::from))
        .unwrap_or_else(|| dirs::home_dir().expect("unable to locate home directory"))
}

fn export<W: Write>(st: &mut ShellState, argv: &[String], out: &mut W) -> Result<BuiltinOutcome> {
    if argv.is_empty() {
        let mut keys: Vec<String> = st.exported_keys().into_iter().map(str::to_string).collect();
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

fn unset(st: &mut ShellState, argv: &[String]) -> Result<BuiltinOutcome> {
    if argv.is_empty() {
        bail!("unset: missing operand");
    }
    for k in argv {
        st.unset(k.as_str());
    }
    Ok(BuiltinOutcome::Status(0))
}

fn sh_quote_value(s: &str) -> String {
    if s.contains(['\'', '\n']) {
        return format!("{}", s.escape_default());
    }
    format!("'{}'", s.replace('\'', r"'\''"))
}
