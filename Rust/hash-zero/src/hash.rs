use crate::cli::{HashAlgorithm, InputJoin, MatchChar, NonceFormat, SharedArgs, ZeroSide, ZeroUnit};
use anyhow::Result;
use sha2::{Digest, Sha256, Sha512};

#[derive(Debug, Clone, Copy)]
pub struct MatchCriteria {
    pub side: ZeroSide,
    pub unit: ZeroUnit,
    pub target: u32,
    pub match_char: MatchChar,
}

impl From<&SharedArgs> for MatchCriteria {
    fn from(shared: &SharedArgs) -> Self {
        Self {
            side: shared.side,
            unit: shared.unit,
            target: shared.zeros,
            match_char: shared.match_char,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct RunInfo {
    pub length: u32,
    pub matched_char: char,
    pub matched_side: ZeroSide,
}

pub fn hash_digest(algorithm: HashAlgorithm, input: &[u8]) -> Vec<u8> {
    match algorithm {
        HashAlgorithm::Sha256 => Sha256::digest(input).to_vec(),
        HashAlgorithm::Sha512 => Sha512::digest(input).to_vec(),
    }
}

pub fn digest_hex(digest: &[u8]) -> String {
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

pub fn max_run_length(algorithm: HashAlgorithm, unit: ZeroUnit) -> u32 {
    let bit_len = match algorithm {
        HashAlgorithm::Sha256 => 256,
        HashAlgorithm::Sha512 => 512,
    };

    match unit {
        ZeroUnit::Bits => bit_len,
        ZeroUnit::Hex => bit_len / 4,
    }
}

pub fn count_run_info(digest: &[u8], criteria: MatchCriteria) -> RunInfo {
    match criteria.side {
        ZeroSide::Any => {
            let leading = count_run_info_for_side(digest, criteria, ZeroSide::Leading);
            let trailing = count_run_info_for_side(digest, criteria, ZeroSide::Trailing);
            if trailing.length > leading.length {
                trailing
            } else {
                leading
            }
        }
        side => count_run_info_for_side(digest, criteria, side),
    }
}

pub fn count_run(digest: &[u8], criteria: MatchCriteria) -> u32 {
    count_run_info(digest, criteria).length
}

pub fn meets_target(digest: &[u8], criteria: MatchCriteria) -> bool {
    count_run(digest, criteria) >= criteria.target
}

pub fn random_prefix(len: usize) -> Result<String> {
    let byte_len = len.div_ceil(2);
    let mut bytes = vec![0u8; byte_len];
    getrandom::fill(&mut bytes).map_err(|error| anyhow::anyhow!("failed to generate random prefix: {error}"))?;
    let hex: String = bytes.iter().map(|byte| format!("{byte:02x}")).collect();
    Ok(hex[..len].to_string())
}

pub fn resolve_find_prefix(prefix: Option<&str>, prefix_len: usize) -> Result<(String, bool)> {
    match prefix {
        Some(value) => Ok((value.to_string(), false)),
        None => Ok((random_prefix(prefix_len)?, true)),
    }
}

pub fn format_nonce(nonce: u64, format: NonceFormat) -> String {
    match format {
        NonceFormat::Decimal => nonce.to_string(),
        NonceFormat::Hex => format!("{nonce:x}"),
    }
}

pub fn build_input(
    prefix: &str,
    nonce: u64,
    nonce_format: NonceFormat,
    join: InputJoin,
) -> String {
    let nonce_str = format_nonce(nonce, nonce_format);
    match join {
        InputJoin::Concat => format!("{prefix}{nonce_str}"),
        InputJoin::Dash => format!("{prefix}-{nonce_str}"),
        InputJoin::Colon => format!("{prefix}:{nonce_str}"),
        InputJoin::Pipe => format!("{prefix}|{nonce_str}"),
    }
}

pub fn verify_input(input: &str, shared: &SharedArgs) -> Result<VerifyOutcome> {
    let criteria = MatchCriteria::from(shared);
    let digest = hash_digest(shared.algorithm, input.as_bytes());
    let run = count_run_info(&digest, criteria);
    Ok(VerifyOutcome {
        input: input.to_string(),
        hash_hex: digest_hex(&digest),
        actual_run: run.length,
        meets_target: run.length >= criteria.target,
        target_run: criteria.target,
        match_char: criteria.match_char,
        matched_char: run.matched_char,
        algorithm: shared.algorithm,
        side: criteria.side,
        matched_side: run.matched_side,
        unit: criteria.unit,
    })
}

#[derive(Debug, Clone)]
pub struct VerifyOutcome {
    pub input: String,
    pub hash_hex: String,
    pub actual_run: u32,
    pub meets_target: bool,
    pub target_run: u32,
    pub match_char: MatchChar,
    pub matched_char: char,
    pub algorithm: HashAlgorithm,
    pub side: ZeroSide,
    pub matched_side: ZeroSide,
    pub unit: ZeroUnit,
}

fn count_run_info_for_side(
    digest: &[u8],
    criteria: MatchCriteria,
    side: ZeroSide,
) -> RunInfo {
    debug_assert!(matches!(side, ZeroSide::Leading | ZeroSide::Trailing));

    match criteria.unit {
        ZeroUnit::Hex => match criteria.match_char {
            MatchChar::Specific(ch) => RunInfo {
                length: count_hex_run_specific(digest, side, ch),
                matched_char: ch,
                matched_side: side,
            },
            MatchChar::Any => {
                let run = count_hex_run_any(digest, side);
                RunInfo {
                    matched_side: side,
                    ..run
                }
            }
        },
        ZeroUnit::Bits => RunInfo {
            length: count_bit_zeroes(digest, side),
            matched_char: '0',
            matched_side: side,
        },
    }
}

fn count_hex_run_specific(digest: &[u8], side: ZeroSide, ch: char) -> u32 {
    let hex = digest_hex(digest);
    let ch = ch.to_ascii_lowercase();
    let matches = |c: char| c.to_ascii_lowercase() == ch;

    match side {
        ZeroSide::Leading => hex.chars().take_while(|c| matches(*c)).count() as u32,
        ZeroSide::Trailing => hex
            .chars()
            .rev()
            .take_while(|c| matches(*c))
            .count() as u32,
        ZeroSide::Any => unreachable!("specific hex run requires leading or trailing side"),
    }
}

fn count_hex_run_any(digest: &[u8], side: ZeroSide) -> RunInfo {
    let hex = digest_hex(digest);
    let first = match side {
        ZeroSide::Leading => hex.chars().next(),
        ZeroSide::Trailing => hex.chars().last(),
        ZeroSide::Any => unreachable!("any-char hex run requires leading or trailing side"),
    };

    let Some(first) = first else {
        return RunInfo {
            length: 0,
            matched_char: '0',
            matched_side: side,
        };
    };

    let matched = first.to_ascii_lowercase();
    let length = match side {
        ZeroSide::Leading => hex
            .chars()
            .take_while(|c| c.to_ascii_lowercase() == matched)
            .count() as u32,
        ZeroSide::Trailing => hex
            .chars()
            .rev()
            .take_while(|c| c.to_ascii_lowercase() == matched)
            .count() as u32,
        ZeroSide::Any => unreachable!("any-char hex run requires leading or trailing side"),
    };

    RunInfo {
        length,
        matched_char: matched,
        matched_side: side,
    }
}

fn count_bit_zeroes(digest: &[u8], side: ZeroSide) -> u32 {
    match side {
        ZeroSide::Leading => count_leading_zero_bits(digest),
        ZeroSide::Trailing => count_trailing_zero_bits(digest),
        ZeroSide::Any => unreachable!("bit run requires leading or trailing side"),
    }
}

fn count_leading_zero_bits(digest: &[u8]) -> u32 {
    let mut count = 0u32;
    for &byte in digest {
        if byte == 0 {
            count += 8;
            continue;
        }
        count += byte.leading_zeros();
        break;
    }
    count
}

fn count_trailing_zero_bits(digest: &[u8]) -> u32 {
    let mut count = 0u32;
    for &byte in digest.iter().rev() {
        if byte == 0 {
            count += 8;
            continue;
        }
        count += byte.trailing_zeros();
        break;
    }
    count
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cli::MatchChar;

    #[test]
    fn build_input_join_formats() {
        assert_eq!(
            build_input("abc", 42, NonceFormat::Decimal, InputJoin::Concat),
            "abc42"
        );
        assert_eq!(
            build_input("abc", 42, NonceFormat::Decimal, InputJoin::Colon),
            "abc:42"
        );
        assert_eq!(
            build_input("abc", 255, NonceFormat::Hex, InputJoin::Dash),
            "abc-ff"
        );
    }

    #[test]
    fn random_prefix_has_expected_length() {
        let prefix = random_prefix(12).expect("random prefix");
        assert_eq!(prefix.len(), 12);
        assert!(prefix.chars().all(|ch| ch.is_ascii_hexdigit()));
    }

    fn criteria(side: ZeroSide, unit: ZeroUnit, target: u32, ch: MatchChar) -> MatchCriteria {
        MatchCriteria {
            side,
            unit,
            target,
            match_char: ch,
        }
    }

    #[test]
    fn leading_hex_zeroes() {
        let digest = vec![0x00, 0x0a, 0xff];
        assert_eq!(
            count_run(
                &digest,
                criteria(ZeroSide::Leading, ZeroUnit::Hex, 1, MatchChar::Specific('0'))
            ),
            3
        );
    }

    #[test]
    fn side_any_picks_longer_run() {
        let digest = vec![0x00, 0x0a, 0x00];
        let run = count_run_info(
            &digest,
            criteria(ZeroSide::Any, ZeroUnit::Hex, 1, MatchChar::Specific('0')),
        );
        assert_eq!(run.length, 3);
        assert_eq!(run.matched_side, ZeroSide::Leading);
    }

    #[test]
    fn side_any_tie_prefers_leading() {
        let digest = vec![0x00, 0x11, 0x00];
        let run = count_run_info(
            &digest,
            criteria(ZeroSide::Any, ZeroUnit::Hex, 1, MatchChar::Specific('0')),
        );
        assert_eq!(run.length, 2);
        assert_eq!(run.matched_side, ZeroSide::Leading);
    }

    #[test]
    fn leading_hex_custom_char() {
        let digest = vec![0xaa, 0xab, 0xff];
        assert_eq!(
            count_run(
                &digest,
                criteria(ZeroSide::Leading, ZeroUnit::Hex, 1, MatchChar::Specific('a'))
            ),
            3
        );
    }

    #[test]
    fn leading_hex_any_char() {
        let digest = vec![0xaa, 0xab, 0xff];
        let run = count_run_info(
            &digest,
            criteria(ZeroSide::Leading, ZeroUnit::Hex, 1, MatchChar::Any),
        );
        assert_eq!(run.length, 3);
        assert_eq!(run.matched_char, 'a');
    }

    #[test]
    fn trailing_hex_any_char() {
        let digest = vec![0xff, 0xbb];
        let run = count_run_info(
            &digest,
            criteria(ZeroSide::Trailing, ZeroUnit::Hex, 1, MatchChar::Any),
        );
        assert_eq!(run.length, 2);
        assert_eq!(run.matched_char, 'b');
    }

    #[test]
    fn trailing_hex_custom_char() {
        let digest = vec![0xff, 0xab, 0xbb];
        assert_eq!(
            count_run(
                &digest,
                criteria(ZeroSide::Trailing, ZeroUnit::Hex, 1, MatchChar::Specific('b'))
            ),
            3
        );
    }

    #[test]
    fn trailing_hex_zeroes() {
        let digest = vec![0xff, 0xa0, 0x00];
        assert_eq!(
            count_run(
                &digest,
                criteria(ZeroSide::Trailing, ZeroUnit::Hex, 1, MatchChar::Specific('0'))
            ),
            3
        );
    }

    #[test]
    fn leading_bit_zeroes_partial_byte() {
        let digest = vec![0x01, 0xff];
        assert_eq!(
            count_run(
                &digest,
                criteria(ZeroSide::Leading, ZeroUnit::Bits, 1, MatchChar::Specific('0'))
            ),
            7
        );
    }

    #[test]
    fn side_any_bits_picks_longer_run() {
        let digest = vec![0x01, 0x00, 0x80];
        let run = count_run_info(
            &digest,
            criteria(ZeroSide::Any, ZeroUnit::Bits, 1, MatchChar::Specific('0')),
        );
        assert_eq!(run.length, 7);
        assert_eq!(run.matched_side, ZeroSide::Leading);
    }

    #[test]
    fn trailing_bit_zeroes_partial_byte() {
        let digest = vec![0xff, 0x80];
        assert_eq!(
            count_run(
                &digest,
                criteria(ZeroSide::Trailing, ZeroUnit::Bits, 1, MatchChar::Specific('0'))
            ),
            7
        );
    }

    #[test]
    fn all_zero_digest_counts_full_width() {
        let digest = vec![0u8; 32];
        assert_eq!(
            count_run(
                &digest,
                criteria(ZeroSide::Leading, ZeroUnit::Bits, 1, MatchChar::Specific('0'))
            ),
            256
        );
        assert_eq!(
            count_run(
                &digest,
                criteria(ZeroSide::Leading, ZeroUnit::Hex, 1, MatchChar::Specific('0'))
            ),
            64
        );
    }

    #[test]
    fn meets_target_boundary() {
        let digest = vec![0x00, 0x10, 0x00];
        let c = criteria(ZeroSide::Leading, ZeroUnit::Hex, 2, MatchChar::Specific('0'));
        assert!(meets_target(&digest, c));
        assert!(!meets_target(
            &digest,
            MatchCriteria { target: 3, ..c }
        ));
    }

    #[test]
    fn meets_target_any_char() {
        let digest = vec![0xcc, 0xcd, 0xff];
        let c = criteria(ZeroSide::Leading, ZeroUnit::Hex, 2, MatchChar::Any);
        assert!(meets_target(&digest, c));
        assert!(!meets_target(
            &digest,
            MatchCriteria { target: 4, ..c }
        ));
    }

    #[test]
    fn format_nonce_hex_is_lowercase() {
        assert_eq!(format_nonce(255, NonceFormat::Hex), "ff");
    }

    #[test]
    fn sha256_known_vector() {
        let digest = hash_digest(HashAlgorithm::Sha256, b"hello");
        assert_eq!(
            digest_hex(&digest),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        );
    }

    #[test]
    fn max_run_length_sha256() {
        assert_eq!(max_run_length(HashAlgorithm::Sha256, ZeroUnit::Bits), 256);
        assert_eq!(max_run_length(HashAlgorithm::Sha256, ZeroUnit::Hex), 64);
    }

    #[test]
    fn verify_reports_custom_char_run() {
        let shared = SharedArgs {
            zeros: 1,
            side: ZeroSide::Leading,
            match_char: MatchChar::Specific('f'),
            unit: ZeroUnit::Hex,
            algorithm: HashAlgorithm::Sha256,
            json: false,
        };
        let outcome = verify_input("test", &shared).unwrap();
        assert_eq!(outcome.match_char, MatchChar::Specific('f'));
    }

    #[test]
    fn match_char_parses_any() {
        assert_eq!("any".parse::<MatchChar>().unwrap(), MatchChar::Any);
        assert_eq!("ANY".parse::<MatchChar>().unwrap(), MatchChar::Any);
    }
}
