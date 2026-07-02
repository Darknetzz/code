use std::collections::BTreeMap;
use std::path::Path;

use anyhow::{bail, Context, Result};
use serde::Deserialize;

use crate::cli::Cli;

#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
enum HostItem {
    Name(String),
    Entry(HostEntry),
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(default)]
pub struct FileConfig {
    pub timeout_s: Option<f64>,
    pub ping: Option<bool>,
    pub nameserver: Option<String>,
    pub dnssec: Option<bool>,
    #[serde(default)]
    hosts: Vec<HostItem>,
    pub tcp: Vec<TcpEntry>,
    pub urls: Vec<UrlEntry>,
}

impl FileConfig {
    fn host_entries(&self) -> Vec<HostEntry> {
        self.hosts
            .iter()
            .map(|item| match item {
                HostItem::Name(name) => HostEntry {
                    name: name.clone(),
                    dns_records: Vec::new(),
                    expected: BTreeMap::new(),
                    ptr_ip: None,
                    dnssec: None,
                    dnssec_require_ad: None,
                },
                HostItem::Entry(entry) => entry.clone(),
            })
            .collect()
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct HostEntry {
    pub name: String,
    #[serde(default)]
    pub dns_records: Vec<String>,
    #[serde(default)]
    pub expected: BTreeMap<String, ExpectedValue>,
    pub ptr_ip: Option<String>,
    pub dnssec: Option<bool>,
    pub dnssec_require_ad: Option<bool>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
pub enum ExpectedValue {
    Single(String),
    Many(Vec<String>),
}

impl ExpectedValue {
    pub fn as_strings(&self) -> Vec<String> {
        match self {
            Self::Single(value) => vec![value.clone()],
            Self::Many(values) => values.clone(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct TcpEntry {
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Clone, Deserialize)]
pub struct UrlEntry {
    pub url: String,
    pub expected_status: Option<u16>,
}

#[derive(Debug, Clone)]
pub struct HostTarget {
    pub name: String,
    pub dns_records: Vec<String>,
    pub expected: BTreeMap<String, ExpectedValue>,
    pub ptr_ip: Option<String>,
    pub dnssec: Option<bool>,
    pub dnssec_require_ad: bool,
}

#[derive(Debug, Clone)]
pub struct RunConfig {
    pub timeout_s: f64,
    pub ping: bool,
    pub default_dnssec: bool,
    pub nameserver: Option<String>,
    pub hosts: Vec<HostTarget>,
    pub tcp: Vec<TcpEntry>,
    pub urls: Vec<UrlEntry>,
    pub using_fallback_targets: bool,
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
    let using_fallback_targets = !has_any_targets(&file, cli);
    let effective = if using_fallback_targets {
        merge_fallback(file)
    } else {
        file
    };

    let mut hosts = normalize_hosts(&effective.host_entries(), &cli.host);
    for host in &mut hosts {
        if host.dns_records.is_empty() {
            host.dns_records = vec!["A".into()];
        }
        for record in &mut host.dns_records {
            *record = record.to_uppercase();
        }
    }

    Ok(RunConfig {
        timeout_s: effective.timeout_s.unwrap_or(cli.timeout),
        ping: effective.ping.unwrap_or(true) && !cli.no_ping,
        default_dnssec: resolve_dnssec_default(cli, &effective),
        nameserver: cli.nameserver.clone().or(effective.nameserver.clone()),
        hosts,
        tcp: normalize_tcp(&effective, &cli.port)?,
        urls: normalize_urls(&effective, &cli.url),
        using_fallback_targets,
    })
}

fn resolve_dnssec_default(cli: &Cli, file: &FileConfig) -> bool {
    if cli.no_dnssec {
        return false;
    }
    if cli.dnssec {
        return true;
    }
    file.dnssec.unwrap_or(true)
}

fn has_any_targets(file: &FileConfig, cli: &Cli) -> bool {
    if !cli.host.is_empty() || !cli.port.is_empty() || !cli.url.is_empty() {
        return true;
    }
    !file.hosts.is_empty() || !file.tcp.is_empty() || !file.urls.is_empty()
}

fn merge_fallback(mut file: FileConfig) -> FileConfig {
    if file.hosts.is_empty() {
        file.hosts = fallback_hosts()
            .into_iter()
            .map(HostItem::Entry)
            .collect();
    }
    if file.tcp.is_empty() {
        file.tcp = fallback_tcp();
    }
    if file.urls.is_empty() {
        file.urls = fallback_urls();
    }
    file
}

fn normalize_hosts(file_hosts: &[HostEntry], cli_hosts: &[String]) -> Vec<HostTarget> {
    let mut results = file_hosts
        .iter()
        .map(|entry| HostTarget {
            name: entry.name.clone(),
            dns_records: entry.dns_records.clone(),
            expected: entry.expected.clone(),
            ptr_ip: entry.ptr_ip.clone(),
            dnssec: entry.dnssec,
            dnssec_require_ad: entry.dnssec_require_ad.unwrap_or(false),
        })
        .collect::<Vec<_>>();

    for host in cli_hosts {
        results.push(HostTarget {
            name: host.clone(),
            dns_records: vec!["A".into()],
            expected: BTreeMap::new(),
            ptr_ip: None,
            dnssec: None,
            dnssec_require_ad: false,
        });
    }
    results
}

fn normalize_tcp(file: &FileConfig, cli_ports: &[String]) -> Result<Vec<TcpEntry>> {
    let mut results = file.tcp.clone();
    for item in cli_ports {
        let (host, port) = parse_port_target(item)?;
        results.push(TcpEntry { host, port });
    }
    Ok(results)
}

fn normalize_urls(file: &FileConfig, cli_urls: &[String]) -> Vec<UrlEntry> {
    let mut results = file.urls.clone();
    for url in cli_urls {
        results.push(UrlEntry {
            url: url.clone(),
            expected_status: None,
        });
    }
    results
}

fn parse_port_target(item: &str) -> Result<(String, u16)> {
    let Some((host, raw_port)) = item.rsplit_once(':') else {
        bail!("Invalid --port value '{item}', expected host:port");
    };
    let port = raw_port
        .parse::<u16>()
        .with_context(|| format!("Invalid port in --port value '{item}'"))?;
    Ok((host.to_string(), port))
}

fn fallback_hosts() -> Vec<HostEntry> {
    vec![
        HostEntry {
            name: "example.com".into(),
            dns_records: vec!["A".into()],
            expected: BTreeMap::new(),
            ptr_ip: None,
            dnssec: None,
            dnssec_require_ad: None,
        },
        HostEntry {
            name: "one.one.one.one".into(),
            dns_records: vec!["A".into()],
            expected: BTreeMap::new(),
            ptr_ip: Some("1.1.1.1".into()),
            dnssec: Some(false),
            dnssec_require_ad: None,
        },
        HostEntry {
            name: "dns.google".into(),
            dns_records: vec!["A".into()],
            expected: BTreeMap::new(),
            ptr_ip: Some("8.8.8.8".into()),
            dnssec: None,
            dnssec_require_ad: None,
        },
    ]
}

fn fallback_tcp() -> Vec<TcpEntry> {
    vec![
        TcpEntry {
            host: "example.com".into(),
            port: 443,
        },
        TcpEntry {
            host: "1.1.1.1".into(),
            port: 53,
        },
        TcpEntry {
            host: "8.8.8.8".into(),
            port: 53,
        },
        TcpEntry {
            host: "1.1.1.1".into(),
            port: 443,
        },
        TcpEntry {
            host: "8.8.8.8".into(),
            port: 443,
        },
    ]
}

fn fallback_urls() -> Vec<UrlEntry> {
    vec![
        UrlEntry {
            url: "https://example.com".into(),
            expected_status: Some(200),
        },
        UrlEntry {
            url: "https://www.cloudflare.com".into(),
            expected_status: Some(200),
        },
        UrlEntry {
            url: "https://www.google.com/generate_204".into(),
            expected_status: Some(204),
        },
    ]
}

pub fn expected_for_record(
    expected: &BTreeMap<String, ExpectedValue>,
    record_type: &str,
) -> Option<Vec<String>> {
    expected
        .get(&record_type.to_uppercase())
        .map(ExpectedValue::as_strings)
}
