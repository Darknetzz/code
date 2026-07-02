use anyhow::{bail, Result};
use clap::{Args, Parser, Subcommand, ValueEnum};
use std::num::NonZeroUsize;

#[derive(Debug, Parser)]
#[command(name = "hash-zero", about = "Find and verify hashes with leading or trailing zeroes")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    /// Brute-force a nonce until hash(prefix + nonce) meets the zero target.
    Find(FindArgs),
    /// Hash a fixed input and check whether it meets the zero target.
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

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum ZeroUnit {
    Hex,
    Bits,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum NonceFormat {
    Decimal,
    Hex,
}

#[derive(Debug, Args)]
pub struct SharedArgs {
    /// Target count of leading or trailing zeroes.
    #[arg(long)]
    pub zeros: u32,

    /// Count zeroes from the start of the digest.
    #[arg(long, group = "side")]
    pub leading: bool,

    /// Count zeroes from the end of the digest.
    #[arg(long, group = "side")]
    pub trailing: bool,

    /// Measure zeroes as hex nibbles or raw bits.
    #[arg(long, value_enum, default_value_t = ZeroUnit::Hex)]
    pub unit: ZeroUnit,

    /// Hash algorithm to use.
    #[arg(long, value_enum, default_value_t = HashAlgorithm::Sha256)]
    pub algorithm: HashAlgorithm,

    /// Emit JSON report.
    #[arg(long)]
    pub json: bool,
}

impl SharedArgs {
    pub fn side(&self) -> ZeroSide {
        if self.trailing {
            ZeroSide::Trailing
        } else {
            ZeroSide::Leading
        }
    }
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
}

#[derive(Debug, Args)]
pub struct VerifyArgs {
    /// Input string to hash.
    pub input: String,

    #[command(flatten)]
    pub shared: SharedArgs,
}

pub fn validate_zero_target(
    algorithm: HashAlgorithm,
    unit: ZeroUnit,
    zeros: u32,
) -> Result<()> {
    let max = crate::hash::max_zeroes(algorithm, unit);
    if zeros == 0 {
        bail!("--zeros must be at least 1");
    }
    if zeros > max {
        bail!("--zeros {zeros} exceeds maximum of {max} for {:?} {:?}", unit, algorithm);
    }
    Ok(())
}
