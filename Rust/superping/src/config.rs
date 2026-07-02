use std::path::Path;

use anyhow::{bail, Context, Result};
use serde::Deserialize;

use crate::cli::{Cli, ProbeModeArg};
use crate::models::ProbeMode;

#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
enum HostItem {
    Name(String),
    Entry(HostEntry),
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(default)]
pub struct FileConfig {
    pub count: Option<u32>,
    pub interval_s: Option<f64>,
    pub timeout_s: Option<f64>,
    pub mode: Option<String>,
    pub port: Option<u16>,
    pub ipv6: Option<bool>,
    pub ptr: Option<bool>,
    pub payload_size: Option<usize>,
    pub ttl: Option<u8>,
    pub subprocess: Option<bool>,
    #[serde(default)]
    hosts: Vec<HostItem>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct HostEntry {
    pub name: String,
    pub port: Option<u16>,
}

#[derive(Debug, Clone)]
pub struct HostTarget {
    pub name: String,
    pub port: Option<u16>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AddressFamily {
    Any,
    V4,
    V6,
}

#[derive(Debug, Clone)]
pub struct RunConfig {
    pub hosts: Vec<HostTarget>,
    pub count: Option<u32>,
    pub interval_s: f64,
    pub timeout_s: f64,
    pub mode: ProbeMode,
    pub port: u16,
    pub address_family: AddressFamily,
    pub ptr: bool,
    pub payload_size: usize,
    pub ttl: Option<u8>,
    pub force_subprocess: bool,
    pub json: bool,
    pub quiet: bool,
}

pub fn load_file_config(path: Option<&Path>) -> Result<FileConfig> {
    let Some(path) = path else {
        return Ok(FileConfig::default());
    };
    let raw = std::fs::read_to_string(path)
        .with_context(|| format!("Config file not found: {}", path.display()))?;
    let loaded: FileConfig = serde_yaml::from_str(&raw)
        .with_context(|| format!("Failed to parse config: {}", path.display()))?;
    Ok(loaded)
}

pub fn build_run_config(cli: &Cli, file: FileConfig) -> Result<RunConfig> {
    let hosts = normalize_hosts(&file, cli)?;
    if hosts.is_empty() {
        bail!("No hosts specified. Use --host, positional HOST args, or a config file with hosts.");
    }

    let mode = parse_mode(file.mode.as_deref(), cli.mode)?;
    let address_family = if cli.ipv6 || file.ipv6.unwrap_or(false) {
        AddressFamily::V6
    } else if cli.ipv4 {
        AddressFamily::V4
    } else {
        AddressFamily::Any
    };

    Ok(RunConfig {
        hosts,
        count: if cli.forever {
            None
        } else {
            Some(file.count.unwrap_or(cli.count))
        },
        interval_s: file.interval_s.unwrap_or(cli.interval),
        timeout_s: file.timeout_s.unwrap_or(cli.timeout),
        mode,
        port: file.port.unwrap_or(cli.port),
        address_family,
        ptr: cli.ptr || file.ptr.unwrap_or(false),
        payload_size: file.payload_size.unwrap_or(cli.payload_size),
        ttl: cli.ttl.or(file.ttl),
        force_subprocess: cli.subprocess || file.subprocess.unwrap_or(false),
        json: cli.json,
        quiet: cli.quiet,
    })
}

fn normalize_hosts(file: &FileConfig, cli: &Cli) -> Result<Vec<HostTarget>> {
    let mut results = file
        .hosts
        .iter()
        .map(|item| match item {
            HostItem::Name(name) => HostTarget {
                name: name.clone(),
                port: None,
            },
            HostItem::Entry(entry) => HostTarget {
                name: entry.name.clone(),
                port: entry.port,
            },
        })
        .collect::<Vec<_>>();

    for host in cli.host.iter().chain(cli.hosts_positional.iter()) {
        if host.contains(':') && !host.starts_with('[') {
            let (name, port) = parse_host_port(host)?;
            results.push(HostTarget { name, port: Some(port) });
        } else {
            results.push(HostTarget {
                name: host.clone(),
                port: None,
            });
        }
    }

    Ok(results)
}

fn parse_host_port(item: &str) -> Result<(String, u16)> {
    let Some((host, raw_port)) = item.rsplit_once(':') else {
        bail!("Invalid host:port value '{item}'");
    };
    let port = raw_port
        .parse::<u16>()
        .with_context(|| format!("Invalid port in '{item}'"))?;
    Ok((host.to_string(), port))
}

fn parse_mode(file_mode: Option<&str>, cli_mode: ProbeModeArg) -> Result<ProbeMode> {
    let mode = match file_mode {
        Some(raw) => match raw.to_ascii_lowercase().as_str() {
            "icmp" => ProbeMode::Icmp,
            "tcp" => ProbeMode::Tcp,
            other => bail!("Invalid mode '{other}', expected icmp or tcp"),
        },
        None => ProbeMode::from(cli_mode),
    };
    Ok(mode)
}
