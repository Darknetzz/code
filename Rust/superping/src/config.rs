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

    let mode = resolve_mode(cli.mode, cli.port, file.mode.as_deref(), file.port, &hosts)?;
    let port = cli.port.or(file.port).unwrap_or(443);
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
        port,
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
            HostItem::Name(name) => parse_target(name),
            HostItem::Entry(entry) => Ok(HostTarget {
                name: entry.name.clone(),
                port: entry.port,
            }),
        })
        .collect::<Result<Vec<_>>>()?;

    for host in cli.host.iter().chain(cli.hosts_positional.iter()) {
        results.push(parse_target(host)?);
    }

    Ok(results)
}

fn parse_target(item: &str) -> Result<HostTarget> {
    let trimmed = item.trim();
    if trimmed.is_empty() {
        bail!("Host target cannot be empty");
    }

    if let Some(target) = parse_bracketed_ipv6_target(trimmed) {
        return Ok(target);
    }

    if let Some((host, port)) = parse_host_port_suffix(trimmed) {
        return Ok(HostTarget {
            name: host,
            port: Some(port),
        });
    }

    Ok(HostTarget {
        name: trimmed.to_string(),
        port: None,
    })
}

fn parse_bracketed_ipv6_target(item: &str) -> Option<HostTarget> {
    let inner = item.strip_prefix('[')?;
    let (host, port_str) = inner.rsplit_once("]:")?;
    let port = port_str.parse::<u16>().ok()?;
    Some(HostTarget {
        name: host.to_string(),
        port: Some(port),
    })
}

fn parse_host_port_suffix(item: &str) -> Option<(String, u16)> {
    let (host, port_str) = item.rsplit_once(':')?;
    if host.is_empty() || host.contains(':') {
        return None;
    }
    let port = port_str.parse::<u16>().ok()?;
    Some((host.to_string(), port))
}

fn resolve_mode(
    cli_mode: Option<ProbeModeArg>,
    cli_port: Option<u16>,
    file_mode: Option<&str>,
    file_port: Option<u16>,
    hosts: &[HostTarget],
) -> Result<ProbeMode> {
    if let Some(mode) = cli_mode {
        return Ok(ProbeMode::from(mode));
    }
    if let Some(raw) = file_mode {
        return parse_mode_str(raw);
    }
    if cli_port.is_some() || file_port.is_some() || hosts.iter().any(|host| host.port.is_some()) {
        return Ok(ProbeMode::Tcp);
    }
    Ok(ProbeMode::Icmp)
}

fn parse_mode_str(raw: &str) -> Result<ProbeMode> {
    match raw.to_ascii_lowercase().as_str() {
        "icmp" => Ok(ProbeMode::Icmp),
        "tcp" => Ok(ProbeMode::Tcp),
        other => bail!("Invalid mode '{other}', expected icmp or tcp"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cli::ProbeModeArg;

    #[test]
    fn port_flag_implies_tcp_mode() {
        let mode = resolve_mode(None, Some(80), None, None, &[]).unwrap();
        assert_eq!(mode, ProbeMode::Tcp);
    }

    #[test]
    fn explicit_mode_overrides_port_implication() {
        let mode = resolve_mode(Some(ProbeModeArg::Icmp), Some(80), None, None, &[]).unwrap();
        assert_eq!(mode, ProbeMode::Icmp);
    }

    #[test]
    fn host_port_implies_tcp_mode() {
        let hosts = vec![HostTarget {
            name: "example.com".into(),
            port: Some(443),
        }];
        let mode = resolve_mode(None, None, None, None, &hosts).unwrap();
        assert_eq!(mode, ProbeMode::Tcp);
    }

    #[test]
    fn defaults_to_icmp_without_port_hints() {
        let mode = resolve_mode(None, None, None, None, &[]).unwrap();
        assert_eq!(mode, ProbeMode::Icmp);
    }

    #[test]
    fn parses_ipv4_host_port_target() {
        let target = parse_target("1.1.1.1:80").unwrap();
        assert_eq!(target.name, "1.1.1.1");
        assert_eq!(target.port, Some(80));
    }

    #[test]
    fn parses_hostname_port_target() {
        let target = parse_target("example.com:443").unwrap();
        assert_eq!(target.name, "example.com");
        assert_eq!(target.port, Some(443));
    }

    #[test]
    fn parses_bracketed_ipv6_host_port_target() {
        let target = parse_target("[2001:db8::1]:80").unwrap();
        assert_eq!(target.name, "2001:db8::1");
        assert_eq!(target.port, Some(80));
    }

    #[test]
    fn bare_ipv6_is_not_treated_as_host_port() {
        let target = parse_target("2001:db8::1").unwrap();
        assert_eq!(target.name, "2001:db8::1");
        assert_eq!(target.port, None);
    }
}
