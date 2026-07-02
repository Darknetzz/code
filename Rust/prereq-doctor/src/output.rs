use comfy_table::{presets::UTF8_FULL, Cell, Color, Table};
use serde_json::json;

use crate::models::{CheckResult, CheckStatus};

pub fn print_human(results: &[CheckResult]) {
    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_header(vec!["Status", "Check", "Version", "Detail"]);

    for result in results {
        let status = Cell::new(result.status.as_str().to_uppercase()).fg(match result.status {
            CheckStatus::Pass => Color::Green,
            CheckStatus::Fail => Color::Red,
            CheckStatus::Warn => Color::Yellow,
        });
        let version = result.version.clone().unwrap_or_else(|| "-".into());
        let mut detail = result.detail.clone().unwrap_or_default();
        if let Some(hint) = &result.hint {
            if !detail.is_empty() {
                detail.push_str("\n");
            }
            detail.push_str(&format!("hint: {hint}"));
        }

        table.add_row(vec![
            status,
            Cell::new(&result.label).fg(Color::Cyan),
            Cell::new(version).fg(Color::DarkGrey),
            Cell::new(detail),
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
        "results": results.iter().map(CheckResult::to_json).collect::<Vec<_>>(),
    });

    println!("{}", serde_json::to_string_pretty(&payload).expect("json"));
}

pub fn print_error(message: &str) {
    eprintln!("FAIL Unable to run checks: {message}");
}
