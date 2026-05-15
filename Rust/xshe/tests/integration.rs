use assert_cmd::Command;
use predicates::str::contains;

fn xshe() -> Command {
    Command::cargo_bin("xshe").expect("cargo_bin xshe")
}

#[test]
fn c_flag_echo() {
    xshe()
        .arg("-c")
        .arg("echo hello")
        .assert()
        .success()
        .stdout(contains("hello"));
}

#[test]
fn export_and_expand_double_quote() {
    xshe()
        .arg("-c")
        .arg("export HELLO=world; echo \"$HELLO\"")
        .assert()
        .success()
        .stdout(contains("world"));
}
#[test]
fn conditional_and_chain() {
    xshe()
        .arg("-c")
        .arg("if true; then echo ok; fi")
        .assert()
        .success()
        .stdout(contains("ok"));
}
