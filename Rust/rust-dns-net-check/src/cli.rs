use clap::Parser;
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "rust-dns-net-check", about = "DNS/network verification tool")]
pub struct Cli {
    /// Path to YAML config file.
    #[arg(long)]
    pub config: Option<PathBuf>,

    /// Host to test (repeatable).
    #[arg(long)]
    pub host: Vec<String>,

    /// TCP target in host:port format (repeatable).
    #[arg(long)]
    pub port: Vec<String>,

    /// URL to probe (repeatable).
    #[arg(long)]
    pub url: Vec<String>,

    /// Default timeout seconds.
    #[arg(long, default_value_t = 5.0)]
    pub timeout: f64,

    /// Emit JSON report.
    #[arg(long)]
    pub json: bool,

    /// Skip ping checks.
    #[arg(long)]
    pub no_ping: bool,

    /// Force-enable DNSSEC check for each host target.
    #[arg(long)]
    pub dnssec: bool,

    /// Disable DNSSEC checks for host targets.
    #[arg(long)]
    pub no_dnssec: bool,

    /// Optional DNS resolver IP to use instead of system default.
    #[arg(long)]
    pub nameserver: Option<String>,
}
