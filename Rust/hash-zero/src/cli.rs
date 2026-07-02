use anyhow::{bail, Result};
use clap::{Args, CommandFactory, Parser, Subcommand, ValueEnum};
use std::io::Write;
use std::num::NonZeroUsize;
use std::str::FromStr;

#[derive(Debug, Parser)]
#[command(
    name = "hash-zero",
    about = "Find and verify hashes with leading or trailing repeating hex characters",
    disable_help_subcommand = true,
    next_line_help = false
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

#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum ZeroSide {
    Leading,
    Trailing,
    Any,
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

    /// Which end of the digest to match from, or `any` for either end.
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

pub fn wants_root_help() -> bool {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        return false;
    }
    let has_help = args.iter().skip(1).any(|arg| arg == "-h" || arg == "--help");
    if !has_help {
        return false;
    }
    !args
        .iter()
        .skip(1)
        .any(|arg| matches!(arg.as_str(), "find" | "verify"))
}

pub fn print_full_help() {
    let mut cmd = Cli::command();
    let stdout = std::io::stdout();
    let mut handle = stdout.lock();

    let _ = write!(
        handle,
        "{}",
        compact_help_text(&cmd.render_help().to_string())
    );

    for sub in cmd.get_subcommands_mut() {
        let name = sub.get_name().to_string();
        let mut section = compact_help_text(&sub.render_help().to_string());
        section = trim_subcommand_about(&section);
        section = trim_subcommand_help_footer(&section);
        section = qualify_subcommand_usage(&name, &section);
        let _ = write!(handle, "\n\n{name}\n{section}");
    }
}

fn trim_subcommand_about(text: &str) -> String {
    let mut lines: Vec<&str> = text.lines().collect();

    if lines.first().is_some_and(|line| !line.starts_with("Usage:")) {
        lines.remove(0);
        while lines.first().is_some_and(|line| line.trim().is_empty()) {
            lines.remove(0);
        }
    }

    lines.join("\n")
}

fn qualify_subcommand_usage(name: &str, text: &str) -> String {
    text.replacen(
        &format!("Usage: {name} "),
        &format!("Usage: hash-zero {name} "),
        1,
    )
}

fn compact_help_text(text: &str) -> String {
    let mut lines = Vec::new();
    let mut prev_blank = false;

    for line in text.lines() {
        if line.trim().is_empty() {
            if !prev_blank {
                lines.push(String::new());
            }
            prev_blank = true;
        } else {
            lines.push(line.to_string());
            prev_blank = false;
        }
    }

    while lines.last().is_some_and(String::is_empty) {
        lines.pop();
    }

    lines.join("\n")
}

fn trim_subcommand_help_footer(text: &str) -> String {
    let mut lines: Vec<&str> = text.lines().collect();

    while let Some(last) = lines.last() {
        if last.trim().is_empty() || last.contains("--help") {
            lines.pop();
        } else {
            break;
        }
    }

    lines.join("\n")
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
