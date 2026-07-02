use anyhow::{bail, Result};
use malachite::Natural;
use malachite::num::arithmetic::traits::Parity;
use malachite::num::basic::traits::One;
use malachite::num::logic::traits::SignificantBits;

use crate::expr::{looks_like_expression, parse_natural};
use crate::progress::ProgressReporter;

const SEQUENCE_WARN_THRESHOLD: u64 = 1_000;

#[derive(Debug, Clone)]
pub struct CollatzResult {
    pub expression: Option<String>,
    pub start: String,
    pub steps: u64,
    pub peak: String,
    pub sequence: Option<Vec<String>>,
    pub sequence_warning: Option<String>,
}

pub fn run_collatz(
    input: &str,
    collect_sequence: bool,
    show_progress: bool,
) -> Result<CollatzResult> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        bail!("input must not be empty");
    }

    let start = parse_natural(trimmed)?;
    let start_text = start.to_string();
    let expression = if looks_like_expression(trimmed) {
        Some(trimmed.to_string())
    } else {
        None
    };

    let mut progress = ProgressReporter::new(show_progress);
    if show_progress {
        progress.status("calculating collatz sequence...");
    }
    let (steps, peak, sequence) = if let Some(value) = natural_to_u128(&start) {
        collatz_u128(value, collect_sequence, &mut progress)
    } else {
        collatz_big(start, collect_sequence, &mut progress)
    };
    progress.finish();

    let sequence_len = sequence.as_ref().map(|values| values.len() as u64);
    let sequence_warning = sequence_len
        .filter(|len| *len > SEQUENCE_WARN_THRESHOLD)
        .map(|len| format!("sequence has {len} values; output may be large"));

    Ok(CollatzResult {
        expression,
        start: start_text,
        steps,
        peak: peak.to_string(),
        sequence,
        sequence_warning,
    })
}

fn natural_to_u128(value: &Natural) -> Option<u128> {
    let max = Natural::from(u128::MAX);
    if value > &max {
        return None;
    }

    value.to_string().parse().ok()
}

fn collatz_u128(
    mut n: u128,
    collect_sequence: bool,
    progress: &mut ProgressReporter,
) -> (u64, Natural, Option<Vec<String>>) {
    let start = n;
    let mut steps = 0u64;
    let mut peak = n;
    let mut sequence = if collect_sequence {
        Some(vec![n.to_string()])
    } else {
        None
    };

    while n != 1 {
        if n % 2 == 0 {
            n /= 2;
        } else if let Some(next) = n.checked_mul(3).and_then(|value| value.checked_add(1)) {
            n = next;
        } else {
            return collatz_big(Natural::from(start), collect_sequence, progress);
        }

        steps += 1;
        if n > peak {
            peak = n;
        }
        if progress.should_report_step(steps) {
            progress.on_step_u128(steps, n, peak);
        }
        if let Some(values) = sequence.as_mut() {
            values.push(n.to_string());
        }
    }

    (steps, Natural::from(peak), sequence)
}

fn collatz_big(
    mut n: Natural,
    collect_sequence: bool,
    progress: &mut ProgressReporter,
) -> (u64, Natural, Option<Vec<String>>) {
    let one = Natural::ONE;
    let three = Natural::from(3u32);
    let mut steps = 0u64;
    let mut peak = n.clone();
    let mut sequence = if collect_sequence {
        Some(vec![n.to_string()])
    } else {
        None
    };

    while n != one {
        if n.even() {
            n >>= 1u32;
        } else {
            n *= &three;
            n += &one;
        }

        steps += 1;
        if n > peak {
            peak = n.clone();
        }
        if progress.should_report_step(steps) {
            progress.on_step_big(steps, n.significant_bits(), peak.significant_bits());
        }
        if let Some(values) = sequence.as_mut() {
            values.push(n.to_string());
        }
    }

    (steps, peak, sequence)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn collatz_27() {
        let result = run_collatz("27", false, false).unwrap();
        assert_eq!(result.steps, 111);
        assert_eq!(result.peak, "9232");
    }

    #[test]
    fn collatz_1() {
        let result = run_collatz("1", false, false).unwrap();
        assert_eq!(result.steps, 0);
        assert_eq!(result.peak, "1");
    }

    #[test]
    fn collatz_expression_power() {
        let result = run_collatz("2^54", false, false).unwrap();
        assert_eq!(result.start, "18014398509481984");
        assert_eq!(result.expression.as_deref(), Some("2^54"));
    }

    #[test]
    fn collatz_expression_product() {
        let result = run_collatz("12340*248", false, false).unwrap();
        assert_eq!(result.start, "3060320");
    }

    #[test]
    fn rejects_zero() {
        assert!(run_collatz("0", false, false).is_err());
    }

    #[test]
    fn rejects_negative() {
        assert!(run_collatz("-5", false, false).is_err());
    }
}
