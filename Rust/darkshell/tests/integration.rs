use assert_cmd::Command;
use assert_cmd::cargo::cargo_bin;
use predicates::str::contains;
use std::process::{Command as StdCommand, Stdio};

fn dsh() -> Command {
    Command::cargo_bin("dsh").expect("cargo_bin dsh")
}

#[test]
fn c_flag_echo() {
    dsh()
        .arg("-c")
        .arg("echo hello")
        .assert()
        .success()
        .stdout(contains("hello"));
}

#[test]
fn export_and_expand_double_quote() {
    dsh()
        .arg("-c")
        .arg("export HELLO=world; echo \"$HELLO\"")
        .assert()
        .success()
        .stdout(contains("world"));
}

#[test]
fn help_builtin_is_dsh_not_cmd() {
    dsh()
        .arg("-c")
        .arg("help")
        .assert()
        .success()
        .stdout(contains("Darkshell (dsh)"))
        .stdout(contains("Builtins:"))
        .stdout(contains("not Windows CMD"));
}

#[test]
fn conditional_and_chain() {
    dsh()
        .arg("-c")
        .arg("if true; then echo ok; fi")
        .assert()
        .success()
        .stdout(contains("ok"));
}

#[test]
fn missing_script_file_errors() {
    dsh()
        .arg("__dsh_no_such_script__.dsh")
        .assert()
        .failure()
        .stderr(contains("script file"));
}

#[test]
fn repl_refuses_non_tty_stdin() {
    let out = StdCommand::new(cargo_bin("dsh"))
        .stdin(Stdio::null())
        .output()
        .expect("spawn dsh");
    assert!(!out.status.success());
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        stderr.contains("standard input is not a terminal"),
        "unexpected stderr: {stderr}"
    );
}
