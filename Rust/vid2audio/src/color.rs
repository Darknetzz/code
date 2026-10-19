use std::env;
use std::io::{self, IsTerminal};

const GREEN: &str = "\x1b[32m";
const RED: &str = "\x1b[31m";
const RESET: &str = "\x1b[0m";

fn color_enabled(stream_is_terminal: bool) -> bool {
    if env::var_os("NO_COLOR").is_some() {
        return false;
    }
    stream_is_terminal
}

fn paint(enabled: bool, code: &str, message: &str) -> String {
    if enabled {
        format!("{code}{message}{RESET}")
    } else {
        message.to_string()
    }
}

pub fn success(message: &str) {
    let text = paint(color_enabled(io::stdout().is_terminal()), GREEN, message);
    println!("{text}");
}

pub fn error(message: &str) {
    let text = paint(color_enabled(io::stderr().is_terminal()), RED, message);
    eprintln!("{text}");
}
