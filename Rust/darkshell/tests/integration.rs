use assert_cmd::Command;
use assert_cmd::cargo::cargo_bin;
use predicates::str::contains;
use std::process::{Command as StdCommand, Stdio};

fn dsh() -> Command {
    Command::cargo_bin("darkshell").expect("cargo_bin darkshell")
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
    let out = StdCommand::new(cargo_bin("darkshell"))
        .stdin(Stdio::null())
        .output()
        .expect("spawn darkshell");
    assert!(!out.status.success());
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        stderr.contains("standard input is not a terminal"),
        "unexpected stderr: {stderr}"
    );
}

#[test]
fn prefix_assign_affects_builtin_expansion() {
    dsh()
        .arg("-c")
        .arg("FOO=bar echo $FOO")
        .assert()
        .success()
        .stdout(contains("bar"));
}

#[test]
fn builtin_redirect_stdout() {
    let out_file = "dsh_integration_out.txt";
    let script = format!("echo hello > {out_file}");
    dsh().arg("-c").arg(script).assert().success();
    let contents = std::fs::read_to_string(out_file).expect("read out file");
    let _ = std::fs::remove_file(out_file);
    assert!(contents.contains("hello"), "contents: {contents}");
}

#[test]
fn non_exported_var_not_in_child_env() {
    #[cfg(windows)]
    let cmd = "DSH_SECRET=hidden export DSH_PUBLIC=visible; cmd /c set DSH_SECRET";
    #[cfg(not(windows))]
    let cmd = "DSH_SECRET=hidden export DSH_PUBLIC=visible; sh -c 'echo $DSH_SECRET'";

    let assert = dsh().arg("-c").arg(cmd).assert().success();
    let stdout = String::from_utf8_lossy(&assert.get_output().stdout);
    assert!(
        !stdout.contains("hidden"),
        "non-exported var leaked to child: {stdout}"
    );
}

#[test]
fn exported_var_visible_to_child() {
    #[cfg(windows)]
    let cmd = "export DSH_PUBLIC=visible; cmd /c set DSH_PUBLIC";
    #[cfg(not(windows))]
    let cmd = "export DSH_PUBLIC=visible; sh -c 'echo $DSH_PUBLIC'";

    dsh()
        .arg("-c")
        .arg(cmd)
        .assert()
        .success()
        .stdout(contains("visible"));
}

#[test]
fn function_with_positional() {
    dsh()
        .arg("-c")
        .arg("greet() { echo $1; }; greet world")
        .assert()
        .success()
        .stdout(contains("world"));
}

#[test]
fn return_from_function() {
    dsh()
        .arg("-c")
        .arg("f() { return 3; echo nope; }; f; echo $?")
        .assert()
        .success()
        .stdout(contains("3\n"));
}

#[test]
fn exit_uses_last_status() {
    dsh()
        .arg("-c")
        .arg("false; exit")
        .assert()
        .code(1);
}

#[test]
fn type_builtin() {
    dsh()
        .arg("-c")
        .arg("type echo")
        .assert()
        .success()
        .stdout(contains("builtin"));
}

#[test]
fn pipeline_external() {
    #[cfg(windows)]
    let cmd = "cmd /c echo hello | findstr hello";
    #[cfg(not(windows))]
    let cmd = "/bin/echo hello | cat";

    dsh()
        .arg("-c")
        .arg(cmd)
        .assert()
        .success()
        .stdout(contains("hello"));
}

#[test]
fn command_substitution_rejected() {
    dsh()
        .arg("-c")
        .arg("echo $(date)")
        .assert()
        .failure()
        .stderr(contains("command substitution"));
}
