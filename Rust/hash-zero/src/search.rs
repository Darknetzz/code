use crate::cli::{FindArgs, HashAlgorithm, ZeroSide, ZeroUnit};
use crate::hash::{build_input, count_zeroes, digest_hex, hash_digest, meets_target};
use crate::output::FindProgress;
use anyhow::Result;
use rayon::prelude::*;
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Instant;

const CHUNK_SIZE: u64 = 16_384;

#[derive(Debug, Clone)]
pub struct FindResult {
    pub nonce: u64,
    pub input: String,
    pub hash_hex: String,
    pub actual_zeroes: u32,
    pub target_zeroes: u32,
    pub algorithm: HashAlgorithm,
    pub side: ZeroSide,
    pub unit: ZeroUnit,
    pub attempts: u64,
    pub elapsed_ms: u128,
    pub hash_rate: u64,
}

pub fn find_hash(args: &FindArgs) -> Result<FindResult> {
    let shared = &args.shared;
    let prefix = Arc::new(args.prefix.clone());
    let found = Arc::new(AtomicBool::new(false));
    let best_zeroes = Arc::new(AtomicU32::new(0));
    let latest_nonce = Arc::new(AtomicU64::new(args.nonce_start));
    let show_progress = args.show_progress();
    let start = Instant::now();
    let mut nonce_cursor = args.nonce_start;
    let mut progress = FindProgress::new(show_progress, args.progress_interval_ms, shared.zeros);

    loop {
        if found.load(Ordering::Relaxed) {
            break;
        }

        let chunk_start = nonce_cursor;
        let chunk_end = nonce_cursor.saturating_add(CHUNK_SIZE);

        let match_result = (chunk_start..chunk_end)
            .into_par_iter()
            .find_map_any(|nonce| {
                if found.load(Ordering::Relaxed) {
                    return None;
                }

                let input = build_input(&prefix, nonce, args.nonce_format);
                let digest = hash_digest(shared.algorithm, input.as_bytes());

                if show_progress {
                    let zeroes = count_zeroes(&digest, shared.side(), shared.unit);
                    best_zeroes.fetch_max(zeroes, Ordering::Relaxed);
                    latest_nonce.store(nonce, Ordering::Relaxed);
                }

                if meets_target(
                    &digest,
                    shared.zeros,
                    shared.side(),
                    shared.unit,
                ) {
                    found.store(true, Ordering::Relaxed);
                    let attempts = nonce.saturating_sub(args.nonce_start).saturating_add(1);
                    Some(FindMatch {
                        nonce,
                        input,
                        digest,
                        attempts,
                    })
                } else {
                    None
                }
            });

        let attempts_so_far = chunk_end.saturating_sub(args.nonce_start);
        if match_result.is_none() {
            progress.maybe_report(
                attempts_so_far,
                start.elapsed(),
                best_zeroes.load(Ordering::Relaxed),
                latest_nonce.load(Ordering::Relaxed),
            );
        }
        nonce_cursor = chunk_end;

        if let Some(found_match) = match_result {
            progress.finish();

            let elapsed = start.elapsed();
            let elapsed_ms = elapsed.as_millis();
            let hash_rate = if elapsed.as_secs_f64() > 0.0 {
                (found_match.attempts as f64 / elapsed.as_secs_f64()) as u64
            } else {
                found_match.attempts
            };

            return Ok(FindResult {
                nonce: found_match.nonce,
                input: found_match.input,
                hash_hex: digest_hex(&found_match.digest),
                actual_zeroes: count_zeroes(
                    &found_match.digest,
                    shared.side(),
                    shared.unit,
                ),
                target_zeroes: shared.zeros,
                algorithm: shared.algorithm,
                side: shared.side(),
                unit: shared.unit,
                attempts: found_match.attempts,
                elapsed_ms,
                hash_rate,
            });
        }
    }

    unreachable!("search loop should always return on first match");
}

struct FindMatch {
    nonce: u64,
    input: String,
    digest: Vec<u8>,
    attempts: u64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cli::{NonceFormat, SharedArgs, ZeroUnit};

    fn test_find_args(prefix: &str, zeros: u32) -> FindArgs {
        FindArgs {
            prefix: prefix.to_string(),
            shared: SharedArgs {
                zeros,
                leading: true,
                trailing: false,
                unit: ZeroUnit::Hex,
                algorithm: HashAlgorithm::Sha256,
                json: false,
            },
            nonce_start: 0,
            nonce_format: NonceFormat::Decimal,
            threads: None,
            progress: false,
            no_progress: true,
            progress_interval_ms: 1000,
        }
    }

    #[test]
    fn finds_single_leading_hex_zero_quickly() {
        let result = find_hash(&test_find_args("hz", 1)).expect("should find a match");
        assert!(result.actual_zeroes >= 1);
        assert!(result.hash_hex.starts_with('0'));
        assert!(result.input.starts_with("hz"));
    }
}
