use serde::Serialize;
use std::io::Write;
use std::time::{Duration, Instant};

use crate::cli::{HashAlgorithm, MatchChar, ZeroSide, ZeroUnit};
use crate::hash::VerifyOutcome;
use crate::search::FindResult;

pub fn print_error(message: &str) {
    eprintln!("FAIL {message}");
}

pub struct FindProgress {
    enabled: bool,
    interval: Duration,
    target_run: u32,
    match_char: MatchChar,
    last_report: Instant,
}

impl FindProgress {
    pub fn new(enabled: bool, interval_ms: u64, target_run: u32, match_char: MatchChar) -> Self {
        Self {
            enabled,
            interval: Duration::from_millis(interval_ms),
            target_run,
            match_char,
            last_report: Instant::now(),
        }
    }

    pub fn maybe_report(
        &mut self,
        attempts: u64,
        elapsed: Duration,
        best_run: u32,
        latest_nonce: u64,
    ) {
        if !self.enabled {
            return;
        }
        if self.last_report.elapsed() < self.interval {
            return;
        }
        self.last_report = Instant::now();

        let rate = if elapsed.as_secs_f64() > 0.0 {
            attempts as f64 / elapsed.as_secs_f64()
        } else {
            attempts as f64
        };

        let char_label = char_filter_label(self.match_char);
        let attempts_label = format_compact(attempts);
        let rate_label = format_compact(rate as u64);
        let _ = write!(
            std::io::stderr(),
            "\rprogress: attempts={attempts_label} elapsed={:.1}s rate={rate_label}/s best={best_run}/{target_run} {char_label} nonce={latest_nonce}   ",
            elapsed.as_secs_f64(),
            target_run = self.target_run,
        );
        let _ = std::io::stderr().flush();
    }

    pub fn finish(&self) {
        if self.enabled {
            let _ = writeln!(std::io::stderr());
        }
    }
}

pub fn print_find_human(result: &FindResult) {
    println!("nonce: {}", result.nonce);
    println!("input: {}", result.input);
    println!("hash: {}", result.hash_hex);
    println!(
        "run: {} x '{}' ({}, {}, {})",
        result.actual_run,
        result.matched_char,
        char_filter_label(result.match_char),
        side_label(result.side),
        unit_label(result.unit)
    );
    println!("attempts: {}", format_compact(result.attempts));
    println!("elapsed_ms: {}", result.elapsed_ms);
    println!("hash_rate: {}/s", format_compact(result.hash_rate));
}

pub fn print_verify_human(outcome: &VerifyOutcome) {
    println!("input: {}", outcome.input);
    println!("hash: {}", outcome.hash_hex);
    println!(
        "run: {} x '{}' ({}, {}, {})",
        outcome.actual_run,
        outcome.matched_char,
        char_filter_label(outcome.match_char),
        side_label(outcome.side),
        unit_label(outcome.unit)
    );
    println!(
        "meets_target: {}",
        if outcome.meets_target { "yes" } else { "no" }
    );
}

pub fn print_find_json(result: &FindResult) {
    let payload = JsonFindReport::from(result);
    println!(
        "{}",
        serde_json::to_string_pretty(&payload).expect("json serialization")
    );
}

pub fn print_verify_json(outcome: &VerifyOutcome) {
    let payload = JsonVerifyReport::from(outcome);
    println!(
        "{}",
        serde_json::to_string_pretty(&payload).expect("json serialization")
    );
}

fn side_label(side: ZeroSide) -> &'static str {
    match side {
        ZeroSide::Leading => "leading",
        ZeroSide::Trailing => "trailing",
    }
}

fn unit_label(unit: ZeroUnit) -> &'static str {
    match unit {
        ZeroUnit::Hex => "hex",
        ZeroUnit::Bits => "bits",
    }
}

fn algorithm_label(algorithm: HashAlgorithm) -> &'static str {
    match algorithm {
        HashAlgorithm::Sha256 => "sha256",
        HashAlgorithm::Sha512 => "sha512",
    }
}

fn char_filter_label(match_char: MatchChar) -> &'static str {
    match match_char {
        MatchChar::Any => "any",
        MatchChar::Specific(_) => "specific",
    }
}

fn char_filter_json(match_char: MatchChar) -> String {
    match match_char {
        MatchChar::Any => "any".to_string(),
        MatchChar::Specific(ch) => ch.to_string(),
    }
}

fn format_compact(n: u64) -> String {
    if n >= 1_000_000 {
        format_scaled(n as f64 / 1_000_000.0, "M")
    } else if n >= 1_000 {
        format_scaled(n as f64 / 1_000.0, "K")
    } else {
        n.to_string()
    }
}

fn format_scaled(value: f64, suffix: &str) -> String {
    if value >= 100.0 {
        format!("{:.0}{suffix}", value)
    } else if value >= 10.0 {
        format!("{:.1}{suffix}", value)
    } else {
        format!("{:.2}{suffix}", value)
    }
}

#[cfg(test)]
mod tests {
    use super::format_compact;

    #[test]
    fn compact_formats_thousands() {
        assert_eq!(format_compact(999), "999");
        assert_eq!(format_compact(1_500), "1.50K");
        assert_eq!(format_compact(45_232), "45.2K");
        assert_eq!(format_compact(156_057), "156K");
    }

    #[test]
    fn compact_formats_millions() {
        assert_eq!(format_compact(1_500_000), "1.50M");
        assert_eq!(format_compact(12_300_000), "12.3M");
        assert_eq!(format_compact(150_000_000), "150M");
    }
}

#[derive(Serialize)]
struct JsonFindReport {
    mode: &'static str,
    algorithm: &'static str,
    side: &'static str,
    unit: &'static str,
    char: String,
    matched_char: char,
    target_run: u32,
    actual_run: u32,
    #[serde(rename = "target_zeroes")]
    target_zeroes: u32,
    #[serde(rename = "actual_zeroes")]
    actual_zeroes: u32,
    meets_target: bool,
    nonce: u64,
    input: String,
    hash: String,
    attempts: u64,
    elapsed_ms: u128,
    hash_rate: u64,
}

#[derive(Serialize)]
struct JsonVerifyReport {
    mode: &'static str,
    algorithm: &'static str,
    side: &'static str,
    unit: &'static str,
    char: String,
    matched_char: char,
    target_run: u32,
    actual_run: u32,
    #[serde(rename = "target_zeroes")]
    target_zeroes: u32,
    #[serde(rename = "actual_zeroes")]
    actual_zeroes: u32,
    meets_target: bool,
    input: String,
    hash: String,
}

impl From<&FindResult> for JsonFindReport {
    fn from(result: &FindResult) -> Self {
        Self {
            mode: "find",
            algorithm: algorithm_label(result.algorithm),
            side: side_label(result.side),
            unit: unit_label(result.unit),
            char: char_filter_json(result.match_char),
            matched_char: result.matched_char,
            target_run: result.target_run,
            actual_run: result.actual_run,
            target_zeroes: result.target_run,
            actual_zeroes: result.actual_run,
            meets_target: result.actual_run >= result.target_run,
            nonce: result.nonce,
            input: result.input.clone(),
            hash: result.hash_hex.clone(),
            attempts: result.attempts,
            elapsed_ms: result.elapsed_ms,
            hash_rate: result.hash_rate,
        }
    }
}

impl From<&VerifyOutcome> for JsonVerifyReport {
    fn from(outcome: &VerifyOutcome) -> Self {
        Self {
            mode: "verify",
            algorithm: algorithm_label(outcome.algorithm),
            side: side_label(outcome.side),
            unit: unit_label(outcome.unit),
            char: char_filter_json(outcome.match_char),
            matched_char: outcome.matched_char,
            target_run: outcome.target_run,
            actual_run: outcome.actual_run,
            target_zeroes: outcome.target_run,
            actual_zeroes: outcome.actual_run,
            meets_target: outcome.meets_target,
            input: outcome.input.clone(),
            hash: outcome.hash_hex.clone(),
        }
    }
}
