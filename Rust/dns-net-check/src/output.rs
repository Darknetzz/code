use comfy_table::{presets::UTF8_FULL, Cell, Color, Table};
use serde_json::{json, Map, Value};

use crate::models::{CheckResult, CheckStatus};

pub fn print_human(results: &[CheckResult]) {
    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_header(vec!["Status", "Check", "Target", "Latency", "Message"]);

    for result in results {
        let status = Cell::new(result.status.as_str().to_uppercase()).fg(match result.status {
            CheckStatus::Pass => Color::Green,
            CheckStatus::Fail => Color::Red,
            CheckStatus::Warn => Color::Yellow,
        });
        let latency = result
            .latency_ms
            .map(|value| format!("{value:.1}ms"))
            .unwrap_or_else(|| "-".into());
        let mut message = match result.status {
            CheckStatus::Pass => "ok".to_string(),
            _ => result
                .error
                .clone()
                .unwrap_or_else(|| "failed".to_string()),
        };
        if let Some(hint) = &result.hint {
            if result.status == CheckStatus::Fail {
                message.push_str(&format!("\nhint: {hint}"));
            }
        }

        table.add_row(vec![
            status,
            Cell::new(&result.name).fg(Color::Cyan),
            Cell::new(&result.target),
            Cell::new(latency).fg(Color::DarkGrey),
            Cell::new(message),
        ]);
    }

    println!("{table}");

    let passed = results
        .iter()
        .filter(|result| result.status == CheckStatus::Pass)
        .count();
    let failed = results
        .iter()
        .filter(|result| result.status == CheckStatus::Fail)
        .count();
    let warned = results
        .iter()
        .filter(|result| result.status == CheckStatus::Warn)
        .count();
    println!();
    println!(
        "Summary: pass={passed} fail={failed} warn={warned} total={}",
        results.len()
    );
}

pub fn print_json(results: &[CheckResult]) {
    let passed = results
        .iter()
        .filter(|result| result.status == CheckStatus::Pass)
        .count();
    let failed = results
        .iter()
        .filter(|result| result.status == CheckStatus::Fail)
        .count();
    let warned = results
        .iter()
        .filter(|result| result.status == CheckStatus::Warn)
        .count();

    let payload = json!({
        "summary": {
            "pass": passed,
            "fail": failed,
            "warn": warned,
            "total": results.len(),
        },
        "results": results.iter().map(CheckResult::to_json).collect::<Vec<Map<String, Value>>>(),
    });

    println!("{}", serde_json::to_string_pretty(&payload).expect("json"));
}

pub fn print_fallback_notice() {
    println!("No targets supplied; running built-in baseline checks.");
}

pub fn print_error(message: &str) {
    eprintln!("FAIL Unable to run checks: {message}");
}
