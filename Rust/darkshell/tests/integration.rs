use assert_cmd::Command;
use predicates::str::contains;

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
fn conditional_and_chain() {
    dsh()
        .arg("-c")
        .arg("if true; then echo ok; fi")
        .assert()
        .success()
        .stdout(contains("ok"));
}
