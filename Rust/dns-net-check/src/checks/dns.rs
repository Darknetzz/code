use std::net::SocketAddr;
use std::str::FromStr;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use hickory_client::client::AsyncClient;
use hickory_proto::op::{Edns, Message, MessageType, OpCode, Query};
use hickory_proto::rr::{Name, RData, RecordType};
use hickory_proto::udp::UdpClientStream;
use hickory_proto::xfer::DnsHandle;
use hickory_resolver::config::{NameServerConfig, Protocol, ResolverConfig, ResolverOpts};
use hickory_resolver::error::ResolveErrorKind;
use hickory_proto::xfer::{DnsRequest, DnsRequestOptions, FirstAnswer};
use hickory_resolver::system_conf;
use hickory_resolver::TokioAsyncResolver;
use tokio::net::UdpSocket;

use crate::models::{
    detail_bool, detail_str, detail_strings, details_map, CheckResult,
};

pub struct DnsContext {
    resolver: TokioAsyncResolver,
    nameserver: SocketAddr,
}

impl DnsContext {
    pub fn new(nameserver: Option<&str>, timeout_s: f64) -> Result<Self> {
        let mut opts = ResolverOpts::default();
        opts.timeout = Duration::from_secs_f64(timeout_s);
        opts.attempts = 1;

        let resolved_nameserver = if let Some(ip) = nameserver {
            SocketAddr::from_str(&format!("{ip}:53"))
                .with_context(|| format!("Invalid nameserver IP: {ip}"))?
        } else {
            system_conf::read_system_conf()
                .context("Failed to read system DNS configuration")?
                .0
                .name_servers()
                .first()
                .map(|server| server.socket_addr)
                .ok_or_else(|| anyhow::anyhow!("No DNS nameserver configured"))?
        };

        let resolver = if nameserver.is_some() {
            let mut config = ResolverConfig::new();
            config.add_name_server(NameServerConfig {
                socket_addr: resolved_nameserver,
                protocol: Protocol::Udp,
                tls_dns_name: None,
                trust_negative_responses: false,
                bind_addr: None,
            });
            TokioAsyncResolver::tokio(config, opts)
        } else {
            TokioAsyncResolver::tokio_from_system_conf()?
        };

        Ok(Self {
            resolver,
            nameserver: resolved_nameserver,
        })
    }

    pub async fn check_record(
        &self,
        host: &str,
        record_type: &str,
        expected: Option<Vec<String>>,
        timeout_s: f64,
        check_name: &str,
    ) -> CheckResult {
        let record = match parse_record_type(record_type) {
            Ok(record) => record,
            Err(error) => {
                return CheckResult::fail(
                    check_name,
                    host,
                    None,
                    error,
                    "Use a supported DNS record type.",
                    details_map(),
                );
            }
        };

        let started = Instant::now();
        let lookup = self.resolver.lookup(host, record).await;
        let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;

        let values = match lookup {
            Ok(response) => response
                .iter()
                .map(record_rdata_to_string)
                .collect::<Vec<_>>(),
            Err(error) => {
                return map_resolve_error(check_name, host, &error, timeout_s);
            }
        };

        let mut details = details_map();
        detail_str("record_type", record_type, &mut details);
        detail_strings("values", &values, &mut details);

        if let Some(expected_values) = expected {
            let expected_set = normalize_expected(&expected_values);
            let value_set = normalize_values(&values);
            if !expected_set.iter().all(|item| value_set.contains(item)) {
                detail_strings("expected", &expected_set, &mut details);
                return CheckResult::fail(
                    check_name,
                    host,
                    Some(elapsed_ms),
                    "Resolved records do not match expected values.",
                    "Update DNS records or expected values in config.",
                    details,
                );
            }
            detail_strings("expected", &expected_set, &mut details);
        }

        CheckResult::pass(check_name, host, elapsed_ms, details)
    }

    pub async fn check_cname(
        &self,
        host: &str,
        expected: Option<String>,
        timeout_s: f64,
    ) -> CheckResult {
        let mut result = self
            .check_record(
                host,
                "CNAME",
                expected.map(|value| vec![value]),
                timeout_s,
                "dns_cname",
            )
            .await;
        result.name = "dns_cname".into();
        result
    }

    pub async fn check_ptr(
        &self,
        ip: &str,
        expected: Option<String>,
        timeout_s: f64,
    ) -> CheckResult {
        let reverse_name = match reverse_lookup_name(ip) {
            Ok(name) => name,
            Err(error) => {
                return CheckResult::fail(
                    "dns_ptr",
                    ip,
                    None,
                    error,
                    "Provide a valid IPv4 or IPv6 address.",
                    details_map(),
                );
            }
        };

        let mut result = self
            .check_record(
                &reverse_name,
                "PTR",
                expected.map(|value| vec![value]),
                timeout_s,
                "dns_ptr",
            )
            .await;
        result.name = "dns_ptr".into();
        result.target = ip.into();
        if result.error.is_none() {
            detail_str("reverse_name", reverse_name, &mut result.details);
        }
        result
    }

    pub async fn check_dnssec(
        &self,
        host: &str,
        timeout_s: f64,
        require_ad: bool,
    ) -> CheckResult {
        let started = Instant::now();
        let response = match query_dnskey(host, self.nameserver, timeout_s).await {
            Ok(response) => response,
            Err(error) => {
                return CheckResult::fail(
                    "dns_dnssec",
                    host,
                    None,
                    error,
                    "Check resolver reachability and allow DNS traffic to the resolver.",
                    {
                        let mut details = details_map();
                        detail_str("nameserver", self.nameserver.to_string(), &mut details);
                        details
                    },
                );
            }
        };
        let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;

        let has_dnskey = response
            .answers()
            .iter()
            .any(|record| record.record_type() == RecordType::DNSKEY);
        let has_rrsig = response
            .answers()
            .iter()
            .any(|record| record.record_type() == RecordType::RRSIG);
        let ad_flag = response.authentic_data();

        let mut details = details_map();
        detail_str("nameserver", self.nameserver.to_string(), &mut details);
        detail_bool("dnskey_present", has_dnskey, &mut details);
        detail_bool("rrsig_present", has_rrsig, &mut details);
        detail_bool("ad_flag", ad_flag, &mut details);

        if !has_dnskey {
            return CheckResult::fail(
                "dns_dnssec",
                host,
                Some(elapsed_ms),
                "DNSKEY record not present in answer.",
                "Ensure the zone is DNSSEC-signed and DNSKEY records are published.",
                details,
            );
        }
        if !has_rrsig {
            return CheckResult::fail(
                "dns_dnssec",
                host,
                Some(elapsed_ms),
                "RRSIG record not present in answer.",
                "Ensure signatures are generated and published for DNSKEY RRset.",
                details,
            );
        }
        if require_ad && !ad_flag {
            return CheckResult::fail(
                "dns_dnssec",
                host,
                Some(elapsed_ms),
                "AD (Authenticated Data) flag not set by resolver.",
                "Use a validating resolver or disable strict AD requirement.",
                details,
            );
        }

        CheckResult::pass("dns_dnssec", host, elapsed_ms, details)
    }
}

fn parse_record_type(record_type: &str) -> Result<RecordType, String> {
    record_type
        .parse::<RecordType>()
        .map_err(|_| format!("Unsupported DNS record type: {record_type}"))
}

fn record_rdata_to_string(record: &RData) -> String {
    record.to_string().trim_end_matches('.').to_string()
}

fn normalize_expected(values: &[String]) -> Vec<String> {
    values
        .iter()
        .map(|value| value.trim_end_matches('.').to_string())
        .collect()
}

fn normalize_values(values: &[String]) -> Vec<String> {
    values
        .iter()
        .map(|value| value.trim_end_matches('.').to_string())
        .collect()
}

fn map_resolve_error(
    check_name: &str,
    host: &str,
    error: &hickory_resolver::error::ResolveError,
    timeout_s: f64,
) -> CheckResult {
    let (message, hint) = match error.kind() {
        ResolveErrorKind::NoRecordsFound { .. } => (
            format!("No answer for {host}."),
            "Verify the expected record type exists for this host.",
        ),
        ResolveErrorKind::Timeout => (
            format!("DNS query timed out after {timeout_s}s."),
            "Check resolver reachability and firewall/network policies.",
        ),
        ResolveErrorKind::Proto(error) if error.to_string().contains("NXDOMAIN") => (
            format!("{host} does not exist (NXDOMAIN)."),
            "Verify the hostname spelling and DNS zone configuration.",
        ),
        _ => (
            format!("DNS query failed: {error}"),
            "Check DNS resolver health and request format.",
        ),
    };

    CheckResult::fail(check_name, host, None, message, hint, details_map())
}

fn reverse_lookup_name(ip: &str) -> Result<String, String> {
    if ip.contains(':') {
        return Err(format!("IPv6 PTR checks are not supported yet: {ip}"));
    }
    let octets = ip
        .split('.')
        .map(str::parse::<u8>)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|_| format!("Invalid IPv4 address: {ip}"))?;
    if octets.len() != 4 {
        return Err(format!("Invalid IPv4 address: {ip}"));
    }
    Ok(format!(
        "{}.{}.{}.{}.in-addr.arpa",
        octets[3], octets[2], octets[1], octets[0]
    ))
}

async fn query_dnskey(
    host: &str,
    nameserver: SocketAddr,
    timeout_s: f64,
) -> Result<Message, String> {
    let name = Name::from_ascii(host).map_err(|error| format!("Invalid hostname: {error}"))?;
    let stream = UdpClientStream::<UdpSocket>::with_timeout(
        nameserver,
        Duration::from_secs_f64(timeout_s),
    );
    let (client, background) = AsyncClient::connect(stream)
        .await
        .map_err(|error| format!("DNSSEC query failed: {error}"))?;
    tokio::spawn(background);

    let query = Query::query(name, RecordType::DNSKEY);
    let mut message = Message::new();
    message
        .set_message_type(MessageType::Query)
        .set_op_code(OpCode::Query)
        .set_recursion_desired(true)
        .add_query(query);
    message
        .extensions_mut()
        .get_or_insert_with(Edns::new)
        .set_dnssec_ok(true);

    let mut options = DnsRequestOptions::default();
    options.use_edns = true;

    let response = client
        .send(DnsRequest::new(message, options))
        .first_answer()
        .await
        .map_err(|error| format!("DNSSEC query failed: {error}"))?;

    Ok(response.into_message())
}
