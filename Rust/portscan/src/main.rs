mod ports;
mod scan;

use std::net::Ipv4Addr;
use std::process::ExitCode;
use std::time::Instant;

use anyhow::{bail, Context, Result};
use clap::Parser;

use crate::ports::{parse_ports, DEFAULT_PORTS, PORT_SERVICES};
use crate::scan::scan_host;

#[derive(Parser)]
#[command(
    name = "portscan",
    about = "TCP port scanner (Rust port of Python/pyportscanner)",
    version
)]
struct Cli {
    /// One or more IP addresses to scan
    #[arg(required = true)]
    ips: Vec<String>,

    /// Ports to scan (default: common ports). Format: "80" or "80,443" or "1-1000"
    #[arg(short = 'p', long = "ports")]
    ports: Option<String>,

    /// Connection timeout in seconds
    #[arg(short = 't', long, default_value_t = 1.0)]
    timeout: f64,

    /// Maximum number of concurrent connections
    #[arg(short = 'w', long, default_value_t = 100)]
    workers: usize,
}

fn validate_ip(ip: &str) -> bool {
    ip.parse::<Ipv4Addr>().is_ok()
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => ExitCode::from(code),
        Err(error) => {
            eprintln!("{error:#}");
            ExitCode::from(2)
        }
    }
}

fn run() -> Result<u8> {
    let cli = Cli::parse();

    let valid_ips: Vec<String> = cli
        .ips
        .iter()
        .filter(|ip| {
            if validate_ip(ip) {
                true
            } else {
                eprintln!("[!] Invalid IP address: {ip}");
                false
            }
        })
        .cloned()
        .collect();

    if valid_ips.is_empty() {
        bail!("no valid IP addresses provided");
    }

    let port_list = if let Some(spec) = &cli.ports {
        let parsed = parse_ports(spec);
        if parsed.is_empty() {
            bail!("no valid ports specified");
        }
        parsed
    } else {
        println!("[*] Using default port list ({} ports)", DEFAULT_PORTS.len());
        DEFAULT_PORTS.to_vec()
    };

    let started = chrono_lite_now();
    println!("{}", "=".repeat(60));
    println!("portscan - Started at {started}");
    println!("{}", "=".repeat(60));
    println!("[*] Targets: {}", valid_ips.join(", "));
    println!("[*] Timeout: {}s", cli.timeout);
    println!("[*] Worker limit: {}", cli.workers);

    let t0 = Instant::now();
    let rt = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .context("failed to start async runtime")?;

    let mut results = Vec::new();
    for ip in &valid_ips {
        match rt.block_on(scan_host(ip, &port_list, cli.timeout, cli.workers)) {
            Ok(open_ports) => {
                if open_ports.is_empty() {
                    println!("\n[*] Summary for {ip}: No open ports found");
                } else {
                    println!(
                        "\n[*] Summary for {ip}: {} open port(s)",
                        open_ports.len()
                    );
                }
                results.push((ip.clone(), open_ports));
            }
            Err(error) => {
                eprintln!("\n[!] Error scanning {ip}: {error:#}");
            }
        }
    }

    let duration = t0.elapsed().as_secs_f64();
    println!("\n{}", "=".repeat(60));
    println!("Scan Complete");
    println!("{}", "=".repeat(60));

    for (ip, open_ports) in &results {
        if open_ports.is_empty() {
            println!("\n{ip}: No open ports");
            continue;
        }
        println!("\n{ip}:");
        for port in open_ports {
            let service = PORT_SERVICES
                .iter()
                .find(|(p, _)| *p == *port)
                .map(|(_, name)| *name)
                .unwrap_or("Unknown");
            println!("  {port:5}/tcp - {service}");
        }
    }

    println!("\n[*] Scan completed in {duration:.2} seconds");
    Ok(0)
}

fn chrono_lite_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    // Simple UTC-ish timestamp without chrono dependency
    let days = secs / 86_400;
    let rem = secs % 86_400;
    let hour = rem / 3600;
    let min = (rem % 3600) / 60;
    let sec = rem % 60;
    // Approximate date from epoch days (good enough for scan banner)
    let (y, m, d) = epoch_days_to_ymd(days);
    format!("{y:04}-{m:02}-{d:02} {hour:02}:{min:02}:{sec:02}")
}

fn epoch_days_to_ymd(mut days: u64) -> (u64, u64, u64) {
    // Civil calendar from days since 1970-01-01 (Gregorian)
    days += 719_468;
    let era = days / 146_097;
    let doe = days - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}
