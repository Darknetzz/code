use std::io::{self, Write};

use serde::Serialize;

use crate::collatz::CollatzResult;

#[derive(Serialize)]
struct JsonReport<'a> {
    #[serde(skip_serializing_if = "Option::is_none")]
    expression: Option<&'a str>,
    start: &'a str,
    steps: u64,
    peak: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    sequence: Option<&'a [String]>,
}

pub fn print_error(message: &str) {
    eprintln!("FAIL {message}");
}

pub fn print_sequence_warning(message: &str) {
    eprintln!("WARN {message}");
}

pub fn print_human(result: &CollatzResult, steps_only: bool, show_peak: bool, show_sequence: bool) {
    if let Some(message) = &result.sequence_warning {
        print_sequence_warning(message);
    }

    if show_sequence {
        if let Some(sequence) = &result.sequence {
            for value in sequence {
                println!("{value}");
            }
        }
    }

    if steps_only && !show_peak {
        println!("{}", result.steps);
        let _ = io::stdout().flush();
        return;
    }

    if let Some(expression) = &result.expression {
        println!("expression: {expression}");
        println!("start: {}", result.start);
    }

    if steps_only {
        println!("steps: {}", result.steps);
        if show_peak {
            println!("peak: {}", result.peak);
        }
        return;
    }

    println!("steps: {}", result.steps);

    if show_peak {
        println!("peak: {}", result.peak);
    }
}

pub fn print_json(result: &CollatzResult, include_sequence: bool) {
    if let Some(message) = &result.sequence_warning {
        eprintln!("WARN {message}");
    }

    let payload = JsonReport {
        expression: result.expression.as_deref(),
        start: &result.start,
        steps: result.steps,
        peak: &result.peak,
        sequence: if include_sequence {
            result.sequence.as_deref()
        } else {
            None
        },
    };

    println!(
        "{}",
        serde_json::to_string_pretty(&payload).expect("json serialization")
    );
}
