//! Evaluation/runtime: pipelines, builtins, functions, redirects, control flow.

use std::fs::File;
use std::io::{stderr, stdout, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};

use anyhow::{anyhow, bail, Result};

use crate::ast::*;
use crate::builtins::{is_builtin, run_builtin, BuiltinOutcome};
use crate::expand::expand_word;
use crate::lexer::Lexer;
use crate::parser::parse_program;
use crate::shell::ShellState;
use crate::signals;
use crate::style;

pub fn eval_source(st: &mut ShellState, src: &str) -> Result<()> {
    eval_source_streams(st, src, &mut stdout(), &mut stderr())
}

pub fn eval_source_streams(
    st: &mut ShellState,
    src: &str,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<()> {
    let toks = Lexer::new(src).lex_all()?;
    let prog = parse_program(&toks)?;
    for stmt in &prog.0 {
        run_stmt(st, stmt, out, err)?;
        if st.pending_exit.is_some() {
            break;
        }
    }
    Ok(())
}

pub fn eval_line_streams(
    st: &mut ShellState,
    line: &str,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<()> {
    let trimmed = line.trim_end_matches(['\r', '\n']).trim_start();
    if trimmed.is_empty() || trimmed.starts_with('#') {
        return Ok(());
    }
    let toks = Lexer::new(trimmed).lex_all()?;
    let prog = parse_program(&toks)?;
    for stmt in &prog.0 {
        run_stmt(st, stmt, out, err)?;
        if st.pending_exit.is_some() {
            break;
        }
    }
    Ok(())
}

fn run_stmt(
    st: &mut ShellState,
    stmt: &Stmt,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<()> {
    match stmt {
        Stmt::SemicolonList(list) => run_semilist(st, list, out, err),
        Stmt::While { cond, body } => {
            while run_semilist_status(st, cond, out, err)? == 0 {
                run_semilist(st, body, out, err)?;
                if st.pending_exit.is_some() {
                    break;
                }
            }
            Ok(())
        }
        Stmt::For { var, items, body } => {
            for w in items {
                let val = expand_word(st, w)?;
                st.env.insert(var.clone(), val);
                run_semilist(st, body, out, err)?;
                if st.pending_exit.is_some() {
                    break;
                }
            }
            Ok(())
        }
        Stmt::Function { name, body } => {
            st.functions.insert(name.clone(), body.clone());
            Ok(())
        }
        Stmt::If {
            cond,
            then_part,
            elifs,
            else_part,
        } => {
            if run_semilist_status(st, cond, out, err)? == 0 {
                run_semilist(st, then_part, out, err)
            } else {
                for (c, t) in elifs {
                    if run_semilist_status(st, c, out, err)? == 0 {
                        return run_semilist(st, t, out, err);
                    }
                }
                if let Some(e) = else_part {
                    run_semilist(st, e, out, err)
                } else {
                    Ok(())
                }
            }
        }
    }
}

fn run_semilist(
    st: &mut ShellState,
    list: &SemicolonList,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<()> {
    for ao in &list.0 {
        st.last_status = run_and_or(st, ao, out, err)?;
        if st.pending_exit.is_some() {
            break;
        }
    }
    Ok(())
}

fn run_semilist_status(
    st: &mut ShellState,
    list: &SemicolonList,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<i32> {
    let mut status = st.last_status;
    for ao in &list.0 {
        status = run_and_or(st, ao, out, err)?;
        if st.pending_exit.is_some() {
            break;
        }
    }
    Ok(status)
}

fn run_and_or(
    st: &mut ShellState,
    ao: &AndOrList,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<i32> {
    let mut status = run_pipeline(st, &ao.head, out, err)?;
    for (op, pipe) in &ao.tail {
        if st.pending_exit.is_some() {
            break;
        }
        let go = match op {
            ChainOp::And => status == 0,
            ChainOp::Or => status != 0,
        };
        if go {
            status = run_pipeline(st, pipe, out, err)?;
        }
    }
    Ok(status)
}

fn run_pipeline(
    st: &mut ShellState,
    pipe: &Pipeline,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<i32> {
    if pipe.cmds.len() > 1 {
        for c in &pipe.cmds {
            if !(c.redirects.is_empty() && c.assigns.is_empty()) {
                bail!("dsh: assignments/redirects in multi-command pipelines are not supported yet");
            }
            let head = expanded_head(st, c)?;
            if !head.is_empty() && is_builtin(&head) {
                bail!("dsh: builtins are not supported in pipelines (`{head}`)");
            }
        }
    }

    if pipe.background {
        let mut st2 = st.clone();
        let p = pipe.clone();
        std::thread::spawn(move || {
            let mut o = stdout();
            let mut e = stderr();
            let _ = run_pipeline_fg(&mut st2, &p, &mut o, &mut e);
        });
        Ok(0)
    } else {
        run_pipeline_fg(st, pipe, out, err)
    }
}

fn run_pipeline_fg(
    st: &mut ShellState,
    pipe: &Pipeline,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<i32> {
    let n = pipe.cmds.len();
    if n == 1 {
        return dispatch_simple(st, &pipe.cmds[0], out, err);
    }

    let mut prev_out: Option<std::process::ChildStdout> = None;
    let mut children = Vec::<std::process::Child>::new();

    for (idx, simple) in pipe.cmds.iter().enumerate() {
        let head = expanded_head(st, simple)?;
        let argv = expanded_argv(st, simple)?;
        if head.is_empty() {
            bail!("dsh: empty command in pipeline");
        }
        let mut cmd = Command::new(&head);
        cmd.args(argv.iter().skip(1));
        overlay_env_cmd(st, simple, &mut cmd)?;

        if idx > 0 {
            cmd.stdin(Stdio::from(prev_out.take().unwrap()));
        }
        if idx + 1 < n {
            cmd.stdout(Stdio::piped());
            cmd.stderr(Stdio::inherit());
        }

        let mut child = cmd.spawn().map_err(|e| anyhow!("{head}: {e}"))?;
        if idx + 1 < n {
            prev_out = child.stdout.take();
        }
        children.push(child);
    }

    let mut exit = 1;
    let last = children.len() - 1;
    for (i, mut ch) in children.into_iter().enumerate() {
        if i == last {
            signals::set_child(Some(ch.id()));
            exit = wait_code_child(&mut ch)?;
            signals::set_child(None);
        } else if let Err(e) = ch.wait() {
            return Err(anyhow!(e));
        }
    }
    Ok(exit)
}

fn wait_code_child(ch: &mut std::process::Child) -> Result<i32> {
    Ok(ch.wait()?.code().unwrap_or(127))
}

fn dispatch_simple(
    st: &mut ShellState,
    simple: &SimpleCommand,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<i32> {
    let argv = expanded_argv(st, simple)?;
    if argv.is_empty() {
        apply_redirects_touch_only(st, simple)?;
        return Ok(0);
    }

    let prog = &argv[0];
    if let Some(body) = st.functions.get(prog).cloned() {
        return invoke_function(st, &argv, &body, out, err);
    }

    if is_builtin(prog) {
        match run_builtin(
            st,
            prog,
            simple.argv.get(1..).unwrap_or(&[]),
            out,
        ) {
            Ok(BuiltinOutcome::Status(c)) => Ok(c),
            Ok(BuiltinOutcome::Exit(code)) => {
                st.pending_exit = Some(code);
                Ok(code)
            }
            Err(e) => {
                style::writeln_shell_error(err, &e)?;
                Ok(1)
            }
        }
    } else {
        run_external(st, &argv, simple)
    }
}

fn invoke_function(
    st: &mut ShellState,
    argv: &[String],
    body: &[Stmt],
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<i32> {
    let saved = std::mem::take(&mut st.positional);
    st.positional = argv.iter().skip(1).cloned().collect();
    let mut rc = st.last_status;
    for stmt in body {
        run_stmt(st, stmt, out, err)?;
        rc = st.last_status;
        if st.pending_exit.is_some() {
            break;
        }
    }
    st.positional = saved;
    Ok(rc)
}

fn expanded_argv(st: &mut ShellState, s: &SimpleCommand) -> Result<Vec<String>> {
    let mut out = Vec::with_capacity(s.argv.len());
    for w in &s.argv {
        out.push(expand_word(st, w)?);
    }
    Ok(out)
}

fn expanded_head(st: &mut ShellState, s: &SimpleCommand) -> Result<String> {
    Ok(s
        .argv
        .first()
        .map(|w| expand_word(st, w))
        .transpose()?
        .unwrap_or_default())
}

fn overlay_env_cmd(st: &mut ShellState, simple: &SimpleCommand, cmd: &mut Command) -> Result<()> {
    let mut ovl = Vec::<(String, String)>::new();
    for (k, w) in &simple.assigns {
        ovl.push((k.clone(), expand_word(st, w)?));
    }
    let merged = st.child_env(&ovl);
    for (k, v) in merged {
        cmd.env(k, v);
    }
    Ok(())
}

fn resolved_target(st: &ShellState, w: &Word) -> Result<PathBuf> {
    let raw = expand_word(st, w)?;
    let pb = PathBuf::from(raw);
    Ok(if pb.is_absolute() {
        pb
    } else {
        st.cwd.join(pb)
    })
}

fn open_read_target(st: &ShellState, w: &Word) -> Result<File> {
    Ok(File::open(resolved_target(st, w)?)?)
}

fn open_write_target(st: &ShellState, w: &Word, truncate: bool) -> Result<File> {
    let p = resolved_target(st, w)?;
    if truncate {
        Ok(File::options().write(true).create(true).truncate(true).open(p)?)
    } else {
        Ok(File::options().append(true).create(true).open(p)?)
    }
}

fn apply_redirects_touch_only(st: &ShellState, s: &SimpleCommand) -> Result<()> {
    for r in &s.redirects {
        match r {
            RedirectSpec::OpenRead { fd, target } => {
                if *fd != 0 {
                    bail!("unsupported input redirect on fd {fd}");
                }
                drop(open_read_target(st, target)?);
            }
            RedirectSpec::OpenWrite { fd, truncate, target } => {
                if *fd != 1 {
                    bail!("unsupported output redirect on fd {fd} without a command");
                }
                drop(open_write_target(st, target, *truncate)?);
            }
            RedirectSpec::DupFd { .. } => {
                bail!("dsh: `2>&1` redirection without a command still needs a stdout target file");
            }
        }
    }
    Ok(())
}

fn run_external(st: &mut ShellState, argv: &[String], simple: &SimpleCommand) -> Result<i32> {
    let prog = argv
        .first()
        .expect("run_external with empty argv should be filtered earlier");
    let mut cmd = Command::new(prog);
    cmd.args(argv.iter().skip(1));
    overlay_env_cmd(st, simple, &mut cmd)?;

    let mut stdin = Stdio::inherit();
    let mut out_file: Option<File> = None;
    let mut err_file: Option<File> = None;
    let mut dup_err_to_stdout = false;

    for r in &simple.redirects {
        match r {
            RedirectSpec::OpenRead { fd, target } => {
                if *fd != 0 {
                    bail!("dsh: stdin redirect on fd {fd} is not implemented");
                }
                stdin = Stdio::from(open_read_target(st, target)?);
            }
            RedirectSpec::OpenWrite {
                fd,
                truncate,
                target,
            } => {
                let f = open_write_target(st, target, *truncate)?;
                match *fd {
                    1 => out_file = Some(f),
                    2 => err_file = Some(f),
                    _ => bail!("dsh: unsupported output fd {fd}"),
                }
            }
            RedirectSpec::DupFd {
                fd,
                target_fd,
            } if *fd == 2 && *target_fd == 1 => {
                dup_err_to_stdout = true;
            }
            _ => bail!("dsh: unsupported redirect"),
        }
    }

    let stderr: Stdio = if dup_err_to_stdout {
        match &out_file {
            Some(of) => Stdio::from(
                of.try_clone()
                    .map_err(|e| anyhow!("unable to clone stdout handle for stderr: {e}"))?,
            ),
            None => Stdio::inherit(),
        }
    } else if let Some(ef) = err_file {
        Stdio::from(ef)
    } else {
        Stdio::inherit()
    };

    let stdout: Stdio = if let Some(of) = out_file {
        Stdio::from(of)
    } else {
        Stdio::inherit()
    };

    cmd.stdin(stdin);
    cmd.stdout(stdout);
    cmd.stderr(stderr);

    let mut child = cmd
        .spawn()
        .map_err(|e| anyhow!("{prog}: {e}"))?;
    signals::set_child(Some(child.id()));
    let code = child.wait()?.code().unwrap_or(127);
    signals::set_child(None);
    Ok(code)
}
