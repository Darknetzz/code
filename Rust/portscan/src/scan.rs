use std::net::SocketAddr;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use futures::stream::{self, StreamExt};
use tokio::net::TcpStream;
use tokio::sync::Semaphore;

use crate::ports::{PORT_SERVICES, DEFAULT_PORTS};

pub async fn scan_host(
    ip: &str,
    ports: &[u16],
    timeout_secs: f64,
    max_workers: usize,
) -> Result<Vec<u16>> {
    let total = ports.len();
    let scanned = Arc::new(AtomicUsize::new(0));
    let last_pct = Arc::new(AtomicUsize::new(0));
    let semaphore = Arc::new(Semaphore::new(max_workers.max(1)));
    let timeout = Duration::from_secs_f64(timeout_secs.max(0.01));

    println!("\n[*] Scanning {ip}...");
    println!("[*] Ports to scan: {total}");
    println!("[*] Progress: 0/{total} (0.0%)");

    let mut open_ports = Vec::new();
    let ip_owned = ip.to_string();

    let results: Vec<(u16, bool)> = stream::iter(ports.iter().copied())
        .map(|port| {
            let ip = ip_owned.clone();
            let semaphore = Arc::clone(&semaphore);
            let scanned = Arc::clone(&scanned);
            let last_pct = Arc::clone(&last_pct);
            async move {
                let _permit = semaphore.acquire().await.expect("semaphore");
                let is_open = scan_port(&ip, port, timeout).await;
                let done = scanned.fetch_add(1, Ordering::Relaxed) + 1;
                let pct = (done * 100) / total.max(1);
                let prev = last_pct.load(Ordering::Relaxed);
                if pct > prev || done % 100 == 0 || done == total {
                    last_pct.store(pct, Ordering::Relaxed);
                    let percentage = (done as f64 / total as f64) * 100.0;
                    println!("[*] Progress: {done}/{total} ({percentage:.1}%)");
                }
                (port, is_open)
            }
        })
        .buffer_unordered(max_workers.max(1))
        .collect()
        .await;

    for (port, is_open) in results {
        if is_open {
            open_ports.push(port);
            let service = PORT_SERVICES
                .iter()
                .find(|(p, _)| *p == port)
                .map(|(_, name)| *name)
                .unwrap_or("Unknown");
            println!("[+] Port {port:5} - OPEN ({service})");
        }
    }

    open_ports.sort_unstable();
    Ok(open_ports)
}

async fn scan_port(ip: &str, port: u16, timeout: Duration) -> bool {
    let addr: SocketAddr = match format!("{ip}:{port}").parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    match tokio::time::timeout(timeout, TcpStream::connect(addr)).await {
        Ok(Ok(_)) => true,
        _ => false,
    }
}

#[allow(dead_code)]
pub fn default_ports() -> &'static [u16] {
    DEFAULT_PORTS
}
