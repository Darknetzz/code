use anyhow::{bail, Result};
use clap::{Args, Parser, Subcommand, ValueEnum};
use std::num::NonZeroUsize;
use std::str::FromStr;

#[derive(Debug, Parser)]
#[command(
    name = "hash-zero",
    about = "Find and verify hashes with leading or trailing repeating hex characters"
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    /// Brute-force a nonce until hash(prefix + nonce) meets the match target.
    Find(FindArgs),
    /// Hash a fixed input and check whether it meets the match target.
    Verify(VerifyArgs),
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum HashAlgorithm {
    Sha256,
    Sha512,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum ZeroSide {
    Leading,
    Trailing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum ZeroUnit {
    Hex,
    Bits,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum NonceFormat {
    Decimal,
    Hex,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MatchChar {
    Specific(char),
    Any,
}

impl MatchChar {
    pub fn is_any(self) -> bool {
        matches!(self, Self::Any)
    }
}

impl FromStr for MatchChar {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> Result<Self> {
        if value.eq_ignore_ascii_case("any") {
            return Ok(Self::Any);
        }

        let mut chars = value.chars();
        let ch = chars
            .next()
            .ok_or_else(|| anyhow::anyhow!("--char must be a hex digit or 'any'"))?;
        if chars.next().is_some() {
            bail!("--char must be a single hex digit or 'any'");
        }
        if !ch.is_ascii_hexdigit() {
            bail!("--char must be a hex digit (0-9, a-f) or 'any'");
        }
        Ok(Self::Specific(ch.to_ascii_lowercase()))
    }
}

#[derive(Debug, Args)]
pub struct SharedArgs {
    /// Target length of consecutive matching characters.
    #[arg(long)]
    pub zeros: u32,

    /// Which end of the digest to match from.
    #[arg(long, value_enum, default_value_t = ZeroSide::Leading)]
    pub side: ZeroSide,

    /// Hex digit to match, or `any` for any repeated digit (--unit hex only).
    #[arg(long = "char", default_value = "0")]
    pub match_char: MatchChar,

    /// Measure runs as hex nibbles or raw zero bits.
    #[arg(long, value_enum, default_value_t = ZeroUnit::Hex)]
    pub unit: ZeroUnit,

    /// Hash algorithm to use.
    #[arg(long, value_enum, default_value_t = HashAlgorithm::Sha256)]
    pub algorithm: HashAlgorithm,

    /// Emit JSON report.
    #[arg(long)]
    pub json: bool,
}

#[derive(Debug, Args)]
pub struct FindArgs {
    /// Prefix prepended to each nonce candidate.
    pub prefix: String,

    #[command(flatten)]
    pub shared: SharedArgs,

    /// Starting nonce value.
    #[arg(long, default_value_t = 0)]
    pub nonce_start: u64,

    /// How the nonce is formatted when appended to the prefix.
    #[arg(long, value_enum, default_value_t = NonceFormat::Decimal)]
    pub nonce_format: NonceFormat,

    /// Number of Rayon worker threads (default: all CPUs).
    #[arg(long)]
    pub threads: Option<NonZeroUsize>,

    /// Show live search progress on stderr.
    #[arg(long, action = clap::ArgAction::SetTrue)]
    pub progress: bool,

    /// Suppress live search progress on stderr.
    #[arg(long, action = clap::ArgAction::SetTrue)]
    pub no_progress: bool,

    /// Progress update interval in milliseconds.
    #[arg(long = "progress-interval", default_value_t = 1000, value_name = "MS")]
    pub progress_interval_ms: u64,
}

impl FindArgs {
    pub fn show_progress(&self) -> bool {
        if self.no_progress {
            return false;
        }
        if self.progress {
            return true;
        }
        !self.shared.json
    }
}

#[derive(Debug, Args)]
pub struct VerifyArgs {
    /// Input string to hash.
    pub input: String,

    #[command(flatten)]
    pub shared: SharedArgs,
}

pub fn validate_match_target(shared: &SharedArgs) -> Result<()> {
    let max = crate::hash::max_run_length(shared.algorithm, shared.unit);
    if shared.zeros == 0 {
        bail!("--zeros must be at least 1");
    }
    if shared.zeros > max {
        bail!(
            "--zeros {} exceeds maximum of {max} for {:?} {:?}",
            shared.zeros,
            shared.unit,
            shared.algorithm
        );
    }
    if shared.unit == ZeroUnit::Bits {
        if shared.match_char.is_any() {
            bail!("--char any requires --unit hex; bits mode matches zero bits only");
        }
        if let MatchChar::Specific(ch) = shared.match_char {
            if ch != '0' {
                bail!("--char is only supported with --unit hex; bits mode matches zero bits only");
            }
        }
    }
    Ok(())
}
