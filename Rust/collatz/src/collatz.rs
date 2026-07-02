use anyhow::{bail, Result};
use malachite::Natural;
use malachite::num::arithmetic::traits::Parity;
use malachite::num::basic::traits::{One, Zero};
use std::str::FromStr;

const SEQUENCE_WARN_THRESHOLD: u64 = 1_000;

#[derive(Debug, Clone)]
pub struct CollatzResult {
    pub start: String,
    pub steps: u64,
    pub peak: String,
    pub sequence: Option<Vec<String>>,
    pub sequence_warning: Option<String>,
}

pub fn run_collatz(input: &str, collect_sequence: bool) -> Result<CollatzResult> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        bail!("number must not be empty");
    }
    if trimmed.starts_with('-') {
        bail!("number must be positive");
    }
    if trimmed == "0" || trimmed.starts_with('+') && trimmed[1..].trim() == "0" {
        bail!("number must be greater than zero");
    }

    let start = Natural::from_str(trimmed).map_err(|()| anyhow::anyhow!("invalid decimal integer"))?;
    if start == Natural::ZERO {
        bail!("number must be greater than zero");
    }

    let (steps, peak, sequence) = if let Ok(value) = trimmed.parse::<u128>() {
        collatz_u128(value, collect_sequence)
    } else {
        collatz_big(start.clone(), collect_sequence)
    };

    let sequence_len = sequence.as_ref().map(|values| values.len() as u64);
    let sequence_warning = sequence_len
        .filter(|len| *len > SEQUENCE_WARN_THRESHOLD)
        .map(|len| format!("sequence has {len} values; output may be large"));

    Ok(CollatzResult {
        start: trimmed.to_string(),
        steps,
        peak: peak.to_string(),
        sequence,
        sequence_warning,
    })
}

fn collatz_u128(mut n: u128, collect_sequence: bool) -> (u64, Natural, Option<Vec<String>>) {
    let start = n;
    let mut steps = 0u64;
    let mut peak = Natural::from(n);
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
            return collatz_big(Natural::from(start), collect_sequence);
        }

        steps += 1;
        let current = Natural::from(n);
        if current > peak {
            peak = current;
        }
        if let Some(values) = sequence.as_mut() {
            values.push(n.to_string());
        }
    }

    (steps, peak, sequence)
}

fn collatz_big(mut n: Natural, collect_sequence: bool) -> (u64, Natural, Option<Vec<String>>) {
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
        let result = run_collatz("27", false).unwrap();
        assert_eq!(result.steps, 111);
        assert_eq!(result.peak, "9232");
    }

    #[test]
    fn collatz_1() {
        let result = run_collatz("1", false).unwrap();
        assert_eq!(result.steps, 0);
        assert_eq!(result.peak, "1");
    }

    #[test]
    fn rejects_zero() {
        assert!(run_collatz("0", false).is_err());
    }

    #[test]
    fn rejects_negative() {
        assert!(run_collatz("-5", false).is_err());
    }
}
