use std::path::PathBuf;

use clap::{Parser, ValueEnum};

#[derive(Debug, Clone, Copy, ValueEnum, PartialEq, Eq)]
pub enum ProbeModeArg {
    Icmp,
    Tcp,
}

#[derive(Debug, Parser)]
#[command(name = "superping", about = "ICMP/TCP ping on steroids")]
pub struct Cli {
    /// Path to YAML config file.
    #[arg(long)]
    pub config: Option<PathBuf>,

    /// Target host (repeatable).
    #[arg(long)]
    pub host: Vec<String>,

    /// Positional target hosts.
    #[arg(value_name = "HOST")]
    pub hosts_positional: Vec<String>,

    /// Probes per host.
    #[arg(short = 'c', long, default_value_t = 4)]
    pub count: u32,

    /// Ping until interrupted.
    #[arg(long)]
    pub forever: bool,

    /// Seconds between probes.
    #[arg(short = 'i', long, default_value_t = 1.0)]
    pub interval: f64,

    /// Per-probe timeout in seconds.
    #[arg(long, default_value_t = 5.0)]
    pub timeout: f64,

    /// Probe mode (defaults to tcp when --port is set, otherwise icmp).
    #[arg(long, value_enum)]
    pub mode: Option<ProbeModeArg>,

    /// TCP port (implies --mode tcp when set).
    #[arg(long)]
    pub port: Option<u16>,

    /// Use IPv4 addresses only.
    #[arg(long, conflicts_with = "ipv6")]
    pub ipv4: bool,

    /// Use IPv6 addresses only.
    #[arg(long, conflicts_with = "ipv4")]
    pub ipv6: bool,

    /// Show reverse DNS for resolved IPs.
    #[arg(long)]
    pub ptr: bool,

    /// ICMP payload size in bytes (native mode).
    #[arg(long, default_value_t = 56)]
    pub payload_size: usize,

    /// IP TTL (native ICMP mode).
    #[arg(long)]
    pub ttl: Option<u8>,

    /// Force system ping subprocess instead of native ICMP.
    #[arg(long)]
    pub subprocess: bool,

    /// Emit JSON report.
    #[arg(long)]
    pub json: bool,

    /// Summary only (no per-reply lines).
    #[arg(short, long)]
    pub quiet: bool,
}
