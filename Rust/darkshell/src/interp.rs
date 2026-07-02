//! Evaluation/runtime: pipelines, builtins, functions, redirects, control flow.

use std::fs::File;
use std::io::{stderr, stdout, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use anyhow::{anyhow, bail, Result};

use crate::ast::*;
use crate::builtins::{is_builtin, run_builtin, BuiltinOutcome};
use crate::expand::expand_word;
use crate::lexer::Lexer;
use crate::parser::parse_program;
use crate::shell::{EnvOverlay, ShellState};
use crate::signals;
use crate::style;

pub fn eval_source(st: &mut ShellState, src: &str) -> Result<()> {
    eval_source_streams(st, src, &mut stdout(), &mut stderr())
}

pub fn eval_source_path(st: &mut ShellState, path: &Path) -> Result<()> {
    let contents = std::fs::read_to_string(path)
        .map_err(|e| anyhow!("{}: reading `{}`: {e}", st.argv0, path.display()))?;
    eval_source_streams(
        st,
        &contents,
        &mut stdout(),
        &mut stderr(),
    )
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
                if st.pending_exit.is_some() || st.pending_return.is_some() {
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
                if st.pending_exit.is_some() || st.pending_return.is_some() {
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
        if st.pending_exit.is_some() || st.pending_return.is_some() {
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
        if st.pending_exit.is_some() || st.pending_return.is_some() {
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
        if st.pending_exit.is_some() || st.pending_return.is_some() {
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
                bail!("{}: assignments/redirects in multi-command pipelines are not supported yet", st.argv0);
            }
            let overlay = expand_prefix_overlay(st, c)?;
            let argv0 = st.argv0.clone();
            let env_overlay = EnvOverlay::apply(st, &overlay);
            let head = expanded_head(st, c)?;
            if !head.is_empty() && is_builtin(&head) {
                bail!("{argv0}: builtins are not supported in pipelines (`{head}`)");
            }
            env_overlay.restore(st);
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
        let overlay = expand_prefix_overlay(st, simple)?;
        let argv0 = st.argv0.clone();
        let env_overlay = EnvOverlay::apply(st, &overlay);
        let head = expanded_head(st, simple)?;
        let argv = expanded_argv(st, simple)?;
        env_overlay.restore(st);
        if head.is_empty() {
            bail!("{argv0}: empty command in pipeline");
        }
        let mut cmd = Command::new(&head);
        cmd.args(argv.iter().skip(1));
        apply_child_env(st, &overlay, &mut cmd)?;

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
    let overlay = expand_prefix_overlay(st, simple)?;
    let env_overlay = EnvOverlay::apply(st, &overlay);
    let result = dispatch_simple_with_overlay(st, simple, out, err);
    env_overlay.restore(st);
    result
}

fn dispatch_simple_with_overlay(
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
        return invoke_function(st, &argv, &body, simple, out, err);
    }

    if is_builtin(prog) {
        dispatch_builtin(st, prog, simple, out, err)
    } else {
        run_external(st, &argv, simple)
    }
}

fn dispatch_builtin(
    st: &mut ShellState,
    prog: &str,
    simple: &SimpleCommand,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<i32> {
    let redirects = resolve_output_redirects(st, &simple.redirects)?;
    let args = simple.argv.get(1..).unwrap_or(&[]);

    let mut err_file = redirects.err_file;
    let dup_err = redirects.dup_err_to_stdout;

    let outcome = if let Some(mut out_file) = redirects.out_file {
        run_builtin(st, prog, args, &mut out_file)
    } else {
        run_builtin(st, prog, args, &mut *out)
    };

    match outcome {
        Ok(BuiltinOutcome::Status(c)) => Ok(c),
        Ok(BuiltinOutcome::Exit(code)) => {
            st.pending_exit = Some(code);
            Ok(code)
        }
        Ok(BuiltinOutcome::Return(code)) => {
            st.pending_return = Some(code);
            Ok(code)
        }
        Ok(BuiltinOutcome::Source(path)) => {
            let abs = if path.is_absolute() {
                path
            } else {
                st.cwd.join(path)
            };
            eval_source_path(st, &abs)?;
            Ok(st.last_status)
        }
        Err(e) => {
            if let Some(mut ef) = err_file.take() {
                style::writeln_shell_error(&mut ef, &e)?;
            } else if dup_err {
                style::writeln_shell_error(out, &e)?;
            } else {
                style::writeln_shell_error(err, &e)?;
            }
            Ok(1)
        }
    }
}

fn invoke_function(
    st: &mut ShellState,
    argv: &[String],
    body: &[Stmt],
    _simple: &SimpleCommand,
    out: &mut impl Write,
    err: &mut impl Write,
) -> Result<i32> {
    st.function_depth += 1;
    st.pending_return = None;
    let saved = std::mem::take(&mut st.positional);
    st.positional = argv.iter().skip(1).cloned().collect();
    let mut rc = st.last_status;
    for stmt in body {
        run_stmt(st, stmt, out, err)?;
        rc = st.last_status;
        if st.pending_exit.is_some() || st.pending_return.is_some() {
            break;
        }
    }
    st.positional = saved;
    st.function_depth -= 1;
    if let Some(code) = st.pending_return.take() {
        Ok(code)
    } else {
        Ok(rc)
    }
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

fn expand_prefix_overlay(st: &ShellState, simple: &SimpleCommand) -> Result<Vec<(String, String)>> {
    let mut overlay = Vec::with_capacity(simple.assigns.len());
    for (k, w) in &simple.assigns {
        overlay.push((k.clone(), expand_word(st, w)?));
    }
    Ok(overlay)
}

fn apply_child_env(
    st: &ShellState,
    overlay: &[(String, String)],
    cmd: &mut Command,
) -> Result<()> {
    let merged = st.child_env(overlay);
    for (k, v) in merged {
        cmd.env(k, v);
    }
    Ok(())
}

struct OutputRedirects {
    out_file: Option<File>,
    err_file: Option<File>,
    dup_err_to_stdout: bool,
}

fn resolve_output_redirects(st: &ShellState, redirects: &[RedirectSpec]) -> Result<OutputRedirects> {
    let mut out_file = None;
    let mut err_file = None;
    let mut dup_err_to_stdout = false;
    for r in redirects {
        match r {
            RedirectSpec::OpenRead { fd, .. } => {
                bail!("{}: stdin redirect on fd {fd} is not supported for builtins", st.argv0);
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
                    _ => bail!("{}: unsupported output fd {fd}", st.argv0),
                }
            }
            RedirectSpec::DupFd {
                fd,
                target_fd,
            } if *fd == 2 && *target_fd == 1 => {
                dup_err_to_stdout = true;
            }
            _ => bail!("{}: unsupported redirect", st.argv0),
        }
    }
    Ok(OutputRedirects {
        out_file,
        err_file,
        dup_err_to_stdout,
    })
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
                bail!("{}: `2>&1` redirection without a command still needs a stdout target file", st.argv0);
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
    let overlay = expand_prefix_overlay(st, simple)?;
    apply_child_env(st, &overlay, &mut cmd)?;

    let mut stdin = Stdio::inherit();
    let mut out_file: Option<File> = None;
    let mut err_file: Option<File> = None;
    let mut dup_err_to_stdout = false;

    for r in &simple.redirects {
        match r {
            RedirectSpec::OpenRead { fd, target } => {
                if *fd != 0 {
                    bail!("{}: stdin redirect on fd {fd} is not implemented", st.argv0);
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
                    _ => bail!("{}: unsupported output fd {fd}", st.argv0),
                }
            }
            RedirectSpec::DupFd {
                fd,
                target_fd,
            } if *fd == 2 && *target_fd == 1 => {
                dup_err_to_stdout = true;
            }
            _ => bail!("{}: unsupported redirect", st.argv0),
        }
    }

    let merge_streams = dup_err_to_stdout && out_file.is_none();

    let stderr: Stdio = if dup_err_to_stdout {
        match &out_file {
            Some(of) => Stdio::from(
                of.try_clone()
                    .map_err(|e| anyhow!("unable to clone stdout handle for stderr: {e}"))?,
            ),
            None => Stdio::piped(),
        }
    } else if let Some(ef) = err_file {
        Stdio::from(ef)
    } else {
        Stdio::inherit()
    };

    let stdout: Stdio = if merge_streams {
        Stdio::piped()
    } else if let Some(of) = out_file {
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

    if merge_streams {
        let mut child_out = child
            .stdout
            .take()
            .ok_or_else(|| anyhow!("{prog}: missing stdout pipe"))?;
        let mut child_err = child
            .stderr
            .take()
            .ok_or_else(|| anyhow!("{prog}: missing stderr pipe"))?;
        let out_handle = std::thread::spawn(move || {
            let mut buf = [0u8; 4096];
            let mut dest = std::io::stdout();
            loop {
                match child_out.read(&mut buf) {
                    Ok(0) => break,
                    Ok(n) => {
                        if dest.write_all(&buf[..n]).is_err() {
                            break;
                        }
                    }
                    Err(_) => break,
                }
            }
        });
        let err_handle = std::thread::spawn(move || {
            let mut buf = [0u8; 4096];
            let mut dest = std::io::stdout();
            loop {
                match child_err.read(&mut buf) {
                    Ok(0) => break,
                    Ok(n) => {
                        if dest.write_all(&buf[..n]).is_err() {
                            break;
                        }
                    }
                    Err(_) => break,
                }
            }
        });
        signals::set_child(Some(child.id()));
        let code = child.wait()?.code().unwrap_or(127);
        signals::set_child(None);
        let _ = out_handle.join();
        let _ = err_handle.join();
        return Ok(code);
    }

    signals::set_child(Some(child.id()));
    let code = child.wait()?.code().unwrap_or(127);
    signals::set_child(None);
    Ok(code)
}
