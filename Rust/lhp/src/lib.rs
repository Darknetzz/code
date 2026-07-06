pub mod protocol;
pub mod server;

use std::io::{self, Write};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{bail, Context, Result};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tokio_rustls::rustls::pki_types::{CertificateDer, PrivateKeyDer};
use tokio_rustls::TlsConnector;

use crate::protocol::{create_packet, LhpPacket, TIMESTAMP_WINDOW_SECONDS};

pub async fn send_packet(
    host: &str,
    port: u16,
    cmd_id: u8,
    data: &[u8],
    tls: Option<TlsConnector>,
    cert_path: Option<&str>,
) -> Result<()> {
    let addr = format!("{host}:{port}");
    println!("Connecting to {addr}...");
    let stream = if let Some(connector) = tls {
        let _ = cert_path;
        let domain = rustls::pki_types::ServerName::try_from(host.to_string())
            .map_err(|_| anyhow::anyhow!("invalid server name"))?;
        let stream = TcpStream::connect(&addr).await.context("connect")?;
        let tls_stream = connector.connect(domain, stream).await?;
        ClientStream::Tls(tls_stream)
    } else {
        ClientStream::Plain(TcpStream::connect(&addr).await.context("connect")?)
    };
    println!("Connected to {addr}");
    let packet = create_packet(cmd_id, data);
    match stream {
        ClientStream::Plain(mut s) => {
            s.write_all(&packet).await?;
            s.flush().await?;
        }
        ClientStream::Tls(mut s) => {
            s.write_all(&packet).await?;
            s.flush().await?;
        }
    }
    println!("Sent packet: cmd_id={cmd_id}, payload={data:?}");
    tokio::time::sleep(std::time::Duration::from_millis(100)).await;
    println!("Connection closed");
    Ok(())
}

enum ClientStream {
    Plain(TcpStream),
    Tls(tokio_rustls::client::TlsStream<TcpStream>),
}

impl ClientStream {
    async fn write_all(&mut self, buf: &[u8]) -> io::Result<()> {
        match self {
            Self::Plain(s) => s.write_all(buf).await,
            Self::Tls(s) => s.write_all(buf).await,
        }
    }
    async fn flush(&mut self) -> io::Result<()> {
        match self {
            Self::Plain(s) => s.flush().await,
            Self::Tls(s) => s.flush().await,
        }
    }
}

pub async fn interactive_client(
    host: &str,
    port: u16,
    tls: Option<TlsConnector>,
) -> Result<()> {
    let addr = format!("{host}:{port}");
    println!("Connecting to {addr}...");
    let mut stream = if let Some(connector) = tls {
        let domain = rustls::pki_types::ServerName::try_from(host.to_string())
            .map_err(|_| anyhow::anyhow!("invalid server name"))?;
        let stream = TcpStream::connect(&addr).await?;
        ClientStream::Tls(connector.connect(domain, stream).await?)
    } else {
        ClientStream::Plain(TcpStream::connect(&addr).await?)
    };
    println!("Connected. Enter commands: <cmd_id> <data> (or quit)");
    let stdin = io::stdin();
    loop {
        print!("> ");
        io::stdout().flush()?;
        let mut line = String::new();
        if stdin.read_line(&mut line)? == 0 {
            break;
        }
        let line = line.trim();
        if matches!(line.to_lowercase().as_str(), "quit" | "exit" | "q") {
            break;
        }
        if line.is_empty() {
            continue;
        }
        let (cmd_s, data_s) = match line.split_once(' ') {
            Some((c, d)) => (c, d.as_bytes()),
            None => (line, &[][..]),
        };
        let cmd_id: u16 = cmd_s.parse().context("cmd_id must be 0-255")?;
        if cmd_id > 255 {
            bail!("cmd_id must be 0-255");
        }
        let packet = create_packet(cmd_id as u8, data_s);
        stream.write_all(&packet).await?;
        stream.flush().await?;
        println!("Sent: cmd_id={cmd_id}, data={data_s:?}");
    }
    println!("Disconnected");
    Ok(())
}

pub fn build_tls_client(cert_path: Option<&str>) -> Result<TlsConnector> {
    let mut root_store = tokio_rustls::rustls::RootCertStore::empty();
    if let Some(path) = cert_path {
        let certs = load_certs(path)?;
        for cert in certs {
            root_store.add(cert).context("add CA cert")?;
        }
    }
    let config = tokio_rustls::rustls::ClientConfig::builder()
        .with_root_certificates(root_store)
        .with_no_client_auth();
    Ok(TlsConnector::from(Arc::new(config)))
}

pub fn build_tls_server(cert_path: &str, key_path: &str) -> Result<tokio_rustls::TlsAcceptor> {
    let certs = load_certs(cert_path)?;
    let key = load_private_key(key_path)?;
    let config = tokio_rustls::rustls::ServerConfig::builder()
        .with_no_client_auth()
        .with_single_cert(certs, key)
        .context("TLS server config")?;
    Ok(tokio_rustls::TlsAcceptor::from(Arc::new(config)))
}

fn load_certs(path: &str) -> Result<Vec<CertificateDer<'static>>> {
    let file = std::fs::File::open(path).with_context(|| format!("open {path}"))?;
    let mut reader = std::io::BufReader::new(file);
    let certs = rustls_pemfile::certs(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .context("parse certs")?;
    Ok(certs)
}

fn load_private_key(path: &str) -> Result<PrivateKeyDer<'static>> {
    let file = std::fs::File::open(path).with_context(|| format!("open {path}"))?;
    let mut reader = std::io::BufReader::new(file);
    rustls_pemfile::private_key(&mut reader)?
        .context("no private key found")
}

pub fn parse_packet(bytes: &[u8]) -> Option<LhpPacket> {
    protocol::parse_packet(bytes)
}

pub fn validate_packet(packet: &LhpPacket, seen: &Mutex<std::collections::HashSet<u32>>) -> bool {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as u32)
        .unwrap_or(0);
    let ts = packet.timestamp;
    if ts < now.saturating_sub(TIMESTAMP_WINDOW_SECONDS) {
        println!("Dropped packet: timestamp too old (replay attack?)");
        return false;
    }
    if ts > now.saturating_add(60) {
        println!("Dropped packet: timestamp too far in future");
        return false;
    }
    let mut guard = seen.lock().expect("nonce lock");
    protocol::cleanup_old_nonces(&mut guard, now);
    if guard.contains(&ts) {
        println!("Dropped packet: duplicate nonce detected (replay attack)");
        return false;
    }
    guard.insert(ts);
    let checksum: u8 = packet.payload.iter().fold(0u8, |acc, b| acc ^ b);
    if checksum != packet.checksum {
        println!("Dropped corrupted packet.");
        return false;
    }
    true
}
