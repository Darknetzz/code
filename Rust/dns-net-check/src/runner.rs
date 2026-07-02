use anyhow::Result;

use crate::checks::{check_http, check_ping, check_tcp_connect, DnsContext};
use crate::config::{expected_for_record, RunConfig};
use crate::models::CheckResult;

pub async fn run_checks(config: &RunConfig) -> Result<Vec<CheckResult>> {
    let dns = DnsContext::new(config.nameserver.as_deref(), config.timeout_s)?;
    let mut results = Vec::new();

    for host in &config.hosts {
        for record_type in &host.dns_records {
            let expected = expected_for_record(&host.expected, record_type);
            let check_name = format!("dns_{}", record_type.to_lowercase());
            results.push(
                dns.check_record(
                    &host.name,
                    record_type,
                    expected,
                    config.timeout_s,
                    &check_name,
                )
                .await,
            );
        }

        if let Some(expected) = expected_for_record(&host.expected, "CNAME") {
            results.push(
                dns.check_cname(&host.name, expected.into_iter().next(), config.timeout_s)
                    .await,
            );
        }

        if config.ping {
            let ping_timeout = config.timeout_s.min(5.0);
            results.push(check_ping(&host.name, ping_timeout).await);
        }

        if let Some(ptr_ip) = &host.ptr_ip {
            let expected = expected_for_record(&host.expected, "PTR").and_then(|values| values.into_iter().next());
            results.push(
                dns.check_ptr(ptr_ip, expected, config.timeout_s)
                    .await,
            );
        }

        let do_dnssec = host.dnssec.unwrap_or(config.default_dnssec);
        if do_dnssec {
            results.push(
                dns.check_dnssec(&host.name, config.timeout_s, host.dnssec_require_ad)
                    .await,
            );
        }
    }

    for tcp in &config.tcp {
        results.push(check_tcp_connect(&tcp.host, tcp.port, config.timeout_s).await);
    }

    for url in &config.urls {
        results.push(
            check_http(&url.url, url.expected_status, config.timeout_s).await,
        );
    }

    Ok(results)
}
