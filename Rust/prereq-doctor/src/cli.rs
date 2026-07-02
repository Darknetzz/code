use clap::Parser;
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "prereq-doctor", about = "Check local development and admin prerequisites")]
pub struct Cli {
    /// Optional YAML file with extra checks.
    #[arg(long)]
    pub config: Option<PathBuf>,

    /// Run only checks with these ids (repeatable).
    #[arg(long)]
    pub only: Vec<String>,

    /// Emit JSON report.
    #[arg(long)]
    pub json: bool,

    /// Include optional checks in the failure exit code.
    #[arg(long)]
    pub strict: bool,
}
