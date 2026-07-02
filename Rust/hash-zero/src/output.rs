use serde::Serialize;
use std::io::Write;
use std::time::{Duration, Instant};

use crate::cli::{HashAlgorithm, ZeroSide, ZeroUnit};
use crate::hash::VerifyOutcome;
use crate::search::FindResult;

pub fn print_error(message: &str) {
    eprintln!("FAIL {message}");
}

pub struct FindProgress {
    enabled: bool,
    interval: Duration,
    target_zeroes: u32,
    last_report: Instant,
}

impl FindProgress {
    pub fn new(enabled: bool, interval_ms: u64, target_zeroes: u32) -> Self {
        Self {
            enabled,
            interval: Duration::from_millis(interval_ms),
            target_zeroes,
            last_report: Instant::now(),
        }
    }

    pub fn maybe_report(
        &mut self,
        attempts: u64,
        elapsed: Duration,
        best_zeroes: u32,
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

        let _ = write!(
            std::io::stderr(),
            "\rprogress: attempts={attempts} elapsed={:.1}s rate={rate:.0}/s best={best_zeroes}/{} nonce={latest_nonce}   ",
            elapsed.as_secs_f64(),
            self.target_zeroes,
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
        "zeroes: {} ({}, {})",
        result.actual_zeroes,
        side_label(result.side),
        unit_label(result.unit)
    );
    println!("attempts: {}", result.attempts);
    println!("elapsed_ms: {}", result.elapsed_ms);
    println!("hash_rate: {}/s", result.hash_rate);
}

pub fn print_verify_human(outcome: &VerifyOutcome) {
    println!("input: {}", outcome.input);
    println!("hash: {}", outcome.hash_hex);
    println!(
        "zeroes: {} ({}, {})",
        outcome.actual_zeroes,
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

#[derive(Serialize)]
struct JsonFindReport {
    mode: &'static str,
    algorithm: &'static str,
    side: &'static str,
    unit: &'static str,
    target_zeroes: u32,
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
    target_zeroes: u32,
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
            target_zeroes: result.target_zeroes,
            actual_zeroes: result.actual_zeroes,
            meets_target: result.actual_zeroes >= result.target_zeroes,
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
            target_zeroes: outcome.target_zeroes,
            actual_zeroes: outcome.actual_zeroes,
            meets_target: outcome.meets_target,
            input: outcome.input.clone(),
            hash: outcome.hash_hex.clone(),
        }
    }
}
