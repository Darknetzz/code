use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use tokio::sync::watch;
use tokio::time::sleep;

use crate::config::RunConfig;
use crate::icmp::{is_permission_error, NativeIcmpClient};
use crate::models::{HostProbeResult, PingReply, ProbeMethod, ProbeMode, ResolvedHost};
use crate::output::ReplySink;
use crate::resolve::resolve_hosts;
use crate::stats::compute_stats;
use crate::subprocess::subprocess_ping;
use crate::tcp::tcp_probe;

pub enum ProbeEvent<'a> {
    Header {
        host: &'a ResolvedHost,
        ip: &'a str,
        method: ProbeMethod,
        port: Option<u16>,
    },
    Reply {
        host: &'a ResolvedHost,
        ip: &'a str,
        method: ProbeMethod,
        port: Option<u16>,
        reply: PingReply,
        payload_size: usize,
    },
}

pub async fn run_probes(config: &RunConfig, sink: &mut ReplySink<'_>) -> Result<Vec<HostProbeResult>> {
    let resolved = resolve_hosts(config).await?;
    let (cancel_tx, cancel_rx) = watch::channel(false);
    tokio::spawn(async move {
        if tokio::signal::ctrl_c().await.is_ok() {
            let _ = cancel_tx.send(true);
        }
    });

    if resolved.len() == 1 {
        let host = resolved.into_iter().next().expect("one host");
        let result = probe_host(
            &host,
            config,
            cancel_rx,
            |event| match event {
                ProbeEvent::Header {
                    host,
                    ip,
                    method,
                    port,
                } => sink.print_header(host, ip, method, port),
                ProbeEvent::Reply {
                    host,
                    ip,
                    method,
                    port,
                    reply,
                    payload_size,
                } => sink.print_reply(host, ip, method, port, &reply, payload_size),
            },
        )
        .await?;
        if !config.json && !config.quiet {
            sink.print_host_statistics(&host, &result.resolved_ip, result.port, &result.stats);
        }
        return Ok(vec![result]);
    }

    let shared_config = Arc::new(config.clone());
    let mut tasks = Vec::new();
    for host in resolved {
        let cfg = shared_config.clone();
        let cancel = cancel_rx.clone();
        tasks.push(tokio::spawn(async move {
            probe_host(&host, &cfg, cancel, |_event| {}).await
        }));
    }

    let mut results = Vec::new();
    for task in tasks {
        results.push(task.await??);
    }
    Ok(results)
}

async fn probe_host<F>(
    host: &ResolvedHost,
    config: &RunConfig,
    mut cancel_rx: watch::Receiver<bool>,
    mut on_event: F,
) -> Result<HostProbeResult>
where
    F: FnMut(ProbeEvent<'_>),
{
    let ip_string = host.ip.to_string();
    let port = host.port.unwrap_or(config.port);
    let tcp_port = if config.mode == ProbeMode::Tcp {
        Some(port)
    } else {
        None
    };
    let mut replies = Vec::new();
    let mut interrupted = false;
    let mut method = match config.mode {
        ProbeMode::Tcp => ProbeMethod::Tcp,
        ProbeMode::Icmp if config.force_subprocess => ProbeMethod::SystemPing,
        ProbeMode::Icmp => ProbeMethod::NativeIcmp,
    };

    let native_client = if method == ProbeMethod::NativeIcmp {
        match NativeIcmpClient::new(config.payload_size, config.ttl) {
            Ok(client) => Some(client),
            Err(error) if is_permission_error(&error) => {
                method = ProbeMethod::SystemPing;
                None
            }
            Err(error) => {
                return Ok(failed_result(host, &ip_string, tcp_port, method, error));
            }
        }
    } else {
        None
    };

    on_event(ProbeEvent::Header {
        host,
        ip: &ip_string,
        method,
        port: tcp_port,
    });

    let mut seq = 0u32;
    loop {
        if *cancel_rx.borrow_and_update() {
            interrupted = true;
            break;
        }

        seq += 1;
        let reply = match config.mode {
            ProbeMode::Tcp => tcp_probe(&ip_string, port, seq, config.timeout_s).await,
            ProbeMode::Icmp if method == ProbeMethod::SystemPing => {
                match subprocess_ping(&host.name, config.timeout_s).await {
                    Ok(mut batch) => batch.pop().unwrap_or(timeout_reply(seq)),
                    Err(error) if replies.is_empty() && !is_permission_error(&error) => {
                        return Ok(failed_result(host, &ip_string, tcp_port, method, error));
                    }
                    Err(_) => timeout_reply(seq),
                }
            }
            ProbeMode::Icmp => {
                let client = native_client.as_ref().expect("native client exists");
                match client.ping_once(host.ip, seq, config.timeout_s).await {
                    Ok(reply) => reply,
                    Err(error) if is_permission_error(&error) => {
                        method = ProbeMethod::SystemPing;
                        match subprocess_ping(&host.name, config.timeout_s).await {
                            Ok(mut batch) => batch.pop().unwrap_or(timeout_reply(seq)),
                            Err(sub_error) => {
                                return Ok(failed_result(
                                    host,
                                    &ip_string,
                                    tcp_port,
                                    ProbeMethod::SystemPing,
                                    sub_error,
                                ));
                            }
                        }
                    }
                    Err(error) => {
                        return Ok(failed_result(host, &ip_string, tcp_port, method, error));
                    }
                }
            }
        };

        on_event(ProbeEvent::Reply {
            host,
            ip: &ip_string,
            method,
            port: tcp_port,
            reply: reply.clone(),
            payload_size: config.payload_size,
        });
        replies.push(reply);

        if let Some(count) = config.count {
            if seq >= count {
                break;
            }
        }

        if interrupted {
            break;
        }

        sleep(Duration::from_secs_f64(config.interval_s.max(0.0))).await;
    }

    let stats = compute_stats(seq, &replies);

    Ok(HostProbeResult {
        name: host.name.clone(),
        resolved_ip: ip_string,
        port: tcp_port,
        ptr_name: host.ptr_name.clone(),
        method,
        stats,
        replies,
        interrupted: interrupted,
        error: None,
    })
}

fn timeout_reply(seq: u32) -> PingReply {
    PingReply {
        seq,
        rtt_ms: 0.0,
        ttl: None,
        timed_out: true,
    }
}

fn failed_result(
    host: &ResolvedHost,
    ip: &str,
    port: Option<u16>,
    method: ProbeMethod,
    error: String,
) -> HostProbeResult {
    HostProbeResult {
        name: host.name.clone(),
        resolved_ip: ip.to_string(),
        port,
        ptr_name: host.ptr_name.clone(),
        method,
        stats: compute_stats(0, &[]),
        replies: Vec::new(),
        interrupted: false,
        error: Some(error),
    }
}

#[cfg(test)]
mod tests {
    use std::net::IpAddr;

    use crate::config::{AddressFamily, RunConfig};
    use crate::models::{ProbeMode, ResolvedHost};
    use tokio::sync::watch;

    use super::probe_host;

    #[tokio::test]
    async fn localhost_ping_when_net_tests_enabled() {
        if std::env::var("SUPERPING_RUN_NET_TESTS").ok().as_deref() != Some("1") {
            return;
        }

        let config = RunConfig {
            hosts: vec![],
            count: Some(2),
            interval_s: 0.1,
            timeout_s: 2.0,
            mode: ProbeMode::Icmp,
            port: 443,
            address_family: AddressFamily::Any,
            ptr: false,
            payload_size: 56,
            ttl: None,
            force_subprocess: false,
            json: false,
            quiet: true,
        };
        let host = ResolvedHost {
            name: "127.0.0.1".into(),
            ip: "127.0.0.1".parse::<IpAddr>().unwrap(),
            ptr_name: None,
            port: None,
        };
        let (_tx, rx) = watch::channel(false);
        let result = probe_host(&host, &config, rx, |_event| {})
            .await
            .unwrap();
        assert!(result.ok(), "expected localhost probe to succeed");
    }
}
