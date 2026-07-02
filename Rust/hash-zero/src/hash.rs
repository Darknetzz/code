use crate::cli::{HashAlgorithm, NonceFormat, ZeroSide, ZeroUnit};
use anyhow::Result;
use sha2::{Digest, Sha256, Sha512};

pub fn hash_digest(algorithm: HashAlgorithm, input: &[u8]) -> Vec<u8> {
    match algorithm {
        HashAlgorithm::Sha256 => Sha256::digest(input).to_vec(),
        HashAlgorithm::Sha512 => Sha512::digest(input).to_vec(),
    }
}

pub fn digest_hex(digest: &[u8]) -> String {
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

pub fn max_zeroes(algorithm: HashAlgorithm, unit: ZeroUnit) -> u32 {
    let bit_len = match algorithm {
        HashAlgorithm::Sha256 => 256,
        HashAlgorithm::Sha512 => 512,
    };

    match unit {
        ZeroUnit::Bits => bit_len,
        ZeroUnit::Hex => bit_len / 4,
    }
}

pub fn count_zeroes(digest: &[u8], side: ZeroSide, unit: ZeroUnit) -> u32 {
    match unit {
        ZeroUnit::Hex => count_hex_zeroes(digest, side),
        ZeroUnit::Bits => count_bit_zeroes(digest, side),
    }
}

pub fn meets_target(digest: &[u8], target: u32, side: ZeroSide, unit: ZeroUnit) -> bool {
    count_zeroes(digest, side, unit) >= target
}

pub fn format_nonce(nonce: u64, format: NonceFormat) -> String {
    match format {
        NonceFormat::Decimal => nonce.to_string(),
        NonceFormat::Hex => format!("{nonce:x}"),
    }
}

pub fn build_input(prefix: &str, nonce: u64, format: NonceFormat) -> String {
    format!("{}{}", prefix, format_nonce(nonce, format))
}

pub fn verify_input(
    input: &str,
    algorithm: HashAlgorithm,
    target: u32,
    side: ZeroSide,
    unit: ZeroUnit,
) -> Result<VerifyOutcome> {
    let digest = hash_digest(algorithm, input.as_bytes());
    let actual = count_zeroes(&digest, side, unit);
    Ok(VerifyOutcome {
        input: input.to_string(),
        hash_hex: digest_hex(&digest),
        actual_zeroes: actual,
        meets_target: actual >= target,
        target_zeroes: target,
        algorithm,
        side,
        unit,
    })
}

#[derive(Debug, Clone)]
pub struct VerifyOutcome {
    pub input: String,
    pub hash_hex: String,
    pub actual_zeroes: u32,
    pub meets_target: bool,
    pub target_zeroes: u32,
    pub algorithm: HashAlgorithm,
    pub side: ZeroSide,
    pub unit: ZeroUnit,
}

fn count_hex_zeroes(digest: &[u8], side: ZeroSide) -> u32 {
    let hex = digest_hex(digest);
    match side {
        ZeroSide::Leading => hex.chars().take_while(|ch| *ch == '0').count() as u32,
        ZeroSide::Trailing => hex
            .chars()
            .rev()
            .take_while(|ch| *ch == '0')
            .count() as u32,
    }
}

fn count_bit_zeroes(digest: &[u8], side: ZeroSide) -> u32 {
    match side {
        ZeroSide::Leading => count_leading_zero_bits(digest),
        ZeroSide::Trailing => count_trailing_zero_bits(digest),
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

    #[test]
    fn leading_hex_zeroes() {
        let digest = vec![0x00, 0x0a, 0xff];
        assert_eq!(count_zeroes(&digest, ZeroSide::Leading, ZeroUnit::Hex), 3);
    }

    #[test]
    fn trailing_hex_zeroes() {
        let digest = vec![0xff, 0xa0, 0x00];
        assert_eq!(count_zeroes(&digest, ZeroSide::Trailing, ZeroUnit::Hex), 3);
    }

    #[test]
    fn leading_bit_zeroes_partial_byte() {
        let digest = vec![0x01, 0xff];
        assert_eq!(count_zeroes(&digest, ZeroSide::Leading, ZeroUnit::Bits), 7);
    }

    #[test]
    fn trailing_bit_zeroes_partial_byte() {
        let digest = vec![0xff, 0x80];
        assert_eq!(count_zeroes(&digest, ZeroSide::Trailing, ZeroUnit::Bits), 7);
    }

    #[test]
    fn all_zero_digest_counts_full_width() {
        let digest = vec![0u8; 32];
        assert_eq!(count_zeroes(&digest, ZeroSide::Leading, ZeroUnit::Bits), 256);
        assert_eq!(count_zeroes(&digest, ZeroSide::Leading, ZeroUnit::Hex), 64);
    }

    #[test]
    fn meets_target_boundary() {
        let digest = vec![0x00, 0x10, 0x00];
        assert!(meets_target(&digest, 2, ZeroSide::Leading, ZeroUnit::Hex));
        assert!(!meets_target(&digest, 3, ZeroSide::Leading, ZeroUnit::Hex));
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
    fn max_zeroes_sha256() {
        assert_eq!(max_zeroes(HashAlgorithm::Sha256, ZeroUnit::Bits), 256);
        assert_eq!(max_zeroes(HashAlgorithm::Sha256, ZeroUnit::Hex), 64);
    }

    #[test]
    fn rejects_impossible_target_via_verify() {
        let outcome = verify_input(
            "test",
            HashAlgorithm::Sha256,
            1,
            ZeroSide::Leading,
            ZeroUnit::Hex,
        )
        .unwrap();
        assert!(!outcome.meets_target || outcome.actual_zeroes >= 1);
    }
}
