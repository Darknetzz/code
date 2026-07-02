use crate::cli::FindArgs;
use crate::hash::{build_input, count_run, count_run_info, digest_hex, hash_digest, meets_target, MatchCriteria};
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
    pub actual_run: u32,
    pub target_run: u32,
    pub match_char: crate::cli::MatchChar,
    pub matched_char: char,
    pub algorithm: crate::cli::HashAlgorithm,
    pub side: crate::cli::ZeroSide,
    pub matched_side: crate::cli::ZeroSide,
    pub unit: crate::cli::ZeroUnit,
    pub attempts: u64,
    pub elapsed_ms: u128,
    pub hash_rate: u64,
}

pub fn find_hash(args: &FindArgs) -> Result<FindResult> {
    let shared = &args.shared;
    let criteria = MatchCriteria::from(shared);
    let prefix = Arc::new(args.prefix.clone());
    let found = Arc::new(AtomicBool::new(false));
    let best_run = Arc::new(AtomicU32::new(0));
    let latest_nonce = Arc::new(AtomicU64::new(args.nonce_start));
    let show_progress = args.show_progress();
    let start = Instant::now();
    let mut nonce_cursor = args.nonce_start;
    let mut progress = FindProgress::new(
        show_progress,
        args.progress_interval_ms,
        criteria.target,
        criteria.match_char,
    );

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
                    let run = count_run(&digest, criteria);
                    best_run.fetch_max(run, Ordering::Relaxed);
                    latest_nonce.store(nonce, Ordering::Relaxed);
                }

                if meets_target(&digest, criteria) {
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
                best_run.load(Ordering::Relaxed),
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

            let run = count_run_info(&found_match.digest, criteria);

            return Ok(FindResult {
                nonce: found_match.nonce,
                input: found_match.input,
                hash_hex: digest_hex(&found_match.digest),
                actual_run: run.length,
                target_run: criteria.target,
                match_char: criteria.match_char,
                matched_char: run.matched_char,
                algorithm: shared.algorithm,
                side: criteria.side,
                matched_side: run.matched_side,
                unit: criteria.unit,
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
    use crate::cli::{HashAlgorithm, MatchChar, NonceFormat, SharedArgs, ZeroSide, ZeroUnit};

    fn test_find_args(prefix: &str, zeros: u32) -> FindArgs {
        FindArgs {
            prefix: prefix.to_string(),
            shared: SharedArgs {
                zeros,
                side: ZeroSide::Leading,
                match_char: MatchChar::Specific('0'),
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
        assert!(result.actual_run >= 1);
        assert!(result.hash_hex.starts_with('0'));
        assert!(result.input.starts_with("hz"));
    }

    #[test]
    fn finds_any_char_run_quickly() {
        let mut args = test_find_args("hz", 2);
        args.shared.match_char = MatchChar::Any;
        let result = find_hash(&args).expect("should find a match");
        assert!(result.actual_run >= 2);
        let prefix_len = result
            .hash_hex
            .chars()
            .take(result.actual_run as usize)
            .collect::<String>();
        assert!(prefix_len.chars().all(|c| c == prefix_len.chars().next().unwrap()));
    }
}
