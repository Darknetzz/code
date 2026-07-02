use std::io::{self, Write};

use comfy_table::{presets::UTF8_FULL, Cell, Color, Table};
use serde_json::{json, Value};

use crate::models::{HostProbeResult, PingReply, ProbeMethod, ProbeStats, ResolvedHost};

pub struct ReplySink<'a> {
    quiet: bool,
    json: bool,
    multi_host: bool,
    writer: &'a mut dyn Write,
}

impl<'a> ReplySink<'a> {
    pub fn new(writer: &'a mut dyn Write, quiet: bool, json: bool, multi_host: bool) -> Self {
        Self {
            quiet,
            json,
            multi_host,
            writer,
        }
    }

    fn writeln(&mut self, line: &str) {
        if self.json || self.quiet {
            return;
        }
        let _ = writeln!(self.writer, "{line}");
        let _ = self.writer.flush();
    }

    pub fn print_header(&mut self, host: &ResolvedHost, ip: &str, method: ProbeMethod) {
        if self.json || self.quiet {
            return;
        }
        let mut header = format!("PING {} ({ip}) via {}", host.name, method.as_str());
        if let Some(ptr) = &host.ptr_name {
            header.push_str(&format!(" ptr={ptr}"));
        }
        if self.multi_host {
            header.push_str(" -----");
        }
        self.writeln(&header);
    }

    pub fn print_reply(
        &mut self,
        host: &ResolvedHost,
        ip: &str,
        method: ProbeMethod,
        reply: &PingReply,
        payload_size: usize,
    ) {
        if self.json || self.quiet {
            return;
        }

        let prefix = if self.multi_host {
            format!("[{}] ", host.name)
        } else {
            String::new()
        };

        if reply.timed_out {
            self.writeln(&format!("{prefix}Request timeout for icmp_seq {}", reply.seq));
            return;
        }

        let line = match method {
            ProbeMethod::Tcp => format!(
                "{prefix}Connected to {ip}: seq={} time={:.1} ms",
                reply.seq, reply.rtt_ms
            ),
            _ => {
                let ttl = reply
                    .ttl
                    .map(|value| format!(" ttl={value}"))
                    .unwrap_or_default();
                format!(
                    "{prefix}{payload_size} bytes from {ip}: icmp_seq={}{ttl} time={:.1} ms",
                    reply.seq, reply.rtt_ms
                )
            }
        };
        self.writeln(&line);
    }

    pub fn print_host_statistics(&mut self, host: &ResolvedHost, _ip: &str, stats: &ProbeStats) {
        if self.json || self.quiet {
            return;
        }
        if self.multi_host {
            return;
        }
        print_statistics_block(&mut self.writer, &host.name, stats);
    }
}

pub fn print_statistics_block(writer: &mut dyn Write, host: &str, stats: &ProbeStats) {
    let _ = writeln!(writer);
    let _ = writeln!(writer, "--- {host} ping statistics ---");
    let _ = writeln!(
        writer,
        "{} packets transmitted, {} received, {:.0}% packet loss",
        stats.packets_sent, stats.packets_received, stats.packet_loss_pct
    );
    if let (Some(min), Some(avg), Some(max), Some(stddev), Some(jitter)) = (
        stats.min_ms,
        stats.avg_ms,
        stats.max_ms,
        stats.stddev_ms,
        stats.jitter_ms,
    ) {
        let _ = writeln!(
            writer,
            "rtt min/avg/max/stddev/jitter = {min:.1}/{avg:.1}/{max:.1}/{stddev:.1}/{jitter:.1} ms"
        );
    }
    let _ = writer.flush();
}

pub fn print_summary_table(results: &[HostProbeResult]) {
    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_header(vec![
        "Status",
        "Host",
        "IP",
        "Method",
        "Sent",
        "Recv",
        "Loss%",
        "Avg RTT",
    ]);

    for result in results {
        let status = if result.ok() {
            Cell::new("OK").fg(Color::Green)
        } else {
            Cell::new("FAIL").fg(Color::Red)
        };
        let avg = result
            .stats
            .avg_ms
            .map(|value| format!("{value:.1}ms"))
            .unwrap_or_else(|| "-".into());
        table.add_row(vec![
            status,
            Cell::new(&result.name),
            Cell::new(&result.resolved_ip),
            Cell::new(result.method.as_str()),
            Cell::new(result.stats.packets_sent.to_string()),
            Cell::new(result.stats.packets_received.to_string()),
            Cell::new(format!("{:.0}", result.stats.packet_loss_pct)),
            Cell::new(avg),
        ]);
    }

    println!("{table}");
    let ok = results.iter().filter(|result| result.ok()).count();
    let failed = results.len() - ok;
    println!();
    println!(
        "Summary: ok={ok} failed={failed} total={}",
        results.len()
    );
}

pub fn print_json(results: &[HostProbeResult]) {
    let ok = results.iter().filter(|result| result.ok()).count();
    let failed = results.len() - ok;
    let payload = json!({
        "summary": {
            "hosts": results.len(),
            "ok": ok,
            "failed": failed,
        },
        "hosts": results.iter().map(HostProbeResult::to_json).collect::<Vec<_>>(),
    });
    println!("{}", serde_json::to_string_pretty(&payload).unwrap_or_else(|_| Value::Null.to_string()));
}

pub fn print_human_results(results: &[HostProbeResult], multi_host: bool, quiet: bool) {
    if multi_host {
        if !quiet {
            for result in results {
                if result.replies.is_empty() && result.error.is_some() {
                    println!(
                        "PING {} ({}) FAILED: {}",
                        result.name,
                        result.resolved_ip,
                        result.error.as_deref().unwrap_or("error")
                    );
                    continue;
                }
                print_statistics_block(&mut io::stdout(), &result.name, &result.stats);
            }
        }
        print_summary_table(results);
        return;
    }

    if let Some(result) = results.first() {
        if result.replies.is_empty() {
            if let Some(error) = &result.error {
                println!(
                    "PING {} ({}) FAILED: {error}",
                    result.name, result.resolved_ip
                );
            }
        }
    }
}

pub fn print_error(message: &str) {
    eprintln!("FAIL {message}");
}
