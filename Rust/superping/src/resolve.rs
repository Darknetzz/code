use std::net::IpAddr;

use anyhow::{Context, Result};
use hickory_proto::rr::{RData, RecordType};
use hickory_resolver::TokioAsyncResolver;

use crate::config::{AddressFamily, RunConfig};
use crate::models::ResolvedHost;

pub async fn resolve_hosts(config: &RunConfig) -> Result<Vec<ResolvedHost>> {
    let resolver = build_resolver()?;
    let mut resolved = Vec::new();

    for target in &config.hosts {
        let ips = lookup_host(&resolver, &target.name).await?;
        let ip = pick_address(&ips, config.address_family)
            .with_context(|| format!("No suitable address for {}", target.name))?;

        let ptr_name = if config.ptr {
            reverse_ptr(&resolver, ip).await.ok()
        } else {
            None
        };

        resolved.push(ResolvedHost {
            name: target.name.clone(),
            ip,
            ptr_name,
            port: target.port,
        });
    }

    Ok(resolved)
}

fn build_resolver() -> Result<TokioAsyncResolver> {
    TokioAsyncResolver::tokio_from_system_conf().context("Failed to read system DNS configuration")
}

async fn lookup_host(resolver: &TokioAsyncResolver, host: &str) -> Result<Vec<IpAddr>> {
    if let Ok(ip) = host.parse::<IpAddr>() {
        return Ok(vec![ip]);
    }

    let mut ips = resolver
        .lookup(host, RecordType::A)
        .await
        .ok()
        .map(|lookup| lookup.iter().filter_map(rdata_to_ip).collect::<Vec<_>>())
        .unwrap_or_default();

    if let Ok(lookup) = resolver.lookup(host, RecordType::AAAA).await {
        ips.extend(lookup.iter().filter_map(rdata_to_ip));
    }

    if ips.is_empty() {
        anyhow::bail!("DNS lookup failed for {host}");
    }

    Ok(ips)
}

fn rdata_to_ip(record: &RData) -> Option<IpAddr> {
    match record {
        RData::A(addr) => Some(IpAddr::V4(addr.0)),
        RData::AAAA(addr) => Some(IpAddr::V6(addr.0)),
        _ => None,
    }
}

fn pick_address(ips: &[IpAddr], family: AddressFamily) -> Option<IpAddr> {
    match family {
        AddressFamily::V4 => ips.iter().copied().find(|ip| ip.is_ipv4()),
        AddressFamily::V6 => ips.iter().copied().find(|ip| ip.is_ipv6()),
        AddressFamily::Any => ips
            .iter()
            .copied()
            .find(|ip| ip.is_ipv4())
            .or_else(|| ips.iter().copied().find(|ip| ip.is_ipv6())),
    }
}

async fn reverse_ptr(resolver: &TokioAsyncResolver, ip: IpAddr) -> Result<String> {
    let reverse_name = match ip {
        IpAddr::V4(addr) => {
            let octets = addr.octets();
            format!(
                "{}.{}.{}.{}.in-addr.arpa",
                octets[3], octets[2], octets[1], octets[0]
            )
        }
        IpAddr::V6(addr) => {
            let segments = addr.segments();
            let mut parts = Vec::with_capacity(32);
            for segment in segments.iter().rev() {
                for nibble in (0..4).rev() {
                    parts.push(format!("{:x}", (segment >> (nibble * 4)) & 0xf));
                }
            }
            format!("{}.ip6.arpa", parts.join("."))
        }
    };

    let lookup = resolver
        .lookup(reverse_name, RecordType::PTR)
        .await
        .context("PTR lookup failed")?;

    lookup
        .iter()
        .map(|record| record.to_string().trim_end_matches('.').to_string())
        .next()
        .context("PTR lookup returned no names")
}
