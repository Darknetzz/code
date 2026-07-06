use std::io::{self, Write};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{bail, Context, Result};
use tokio::io::AsyncWriteExt;
use tokio::net::TcpStream;
use tokio_rustls::rustls::pki_types::{CertificateDer, PrivateKeyDer};
use tokio_rustls::TlsConnector;

use crate::protocol::{create_packet, LhpPacket, TIMESTAMP_WINDOW_SECONDS};

pub async fn send_packet(host: &str, port: u16, cmd_id: u8, data: &[u8], tls: Option<TlsConnector>) -> Result<()> {
    let addr = format!("{host}:{port}");
    println!("Connecting to {addr}...");
    let packet = create_packet(cmd_id, data);
    if let Some(connector) = tls {
        let domain = rustls::pki_types::ServerName::try_from(host.to_string())
            .map_err(|_| anyhow::anyhow!("invalid server name"))?;
        let stream = TcpStream::connect(&addr).await.context("connect")?;
        let mut tls_stream = connector.connect(domain, stream).await?;
        tls_stream.write_all(&packet).await?;
        tls_stream.flush().await?;
    } else {
        let mut stream = TcpStream::connect(&addr).await.context("connect")?;
        stream.write_all(&packet).await?;
        stream.flush().await?;
    }
    println!("Connected to {addr}");
    println!("Sent packet: cmd_id={cmd_id}, payload={data:?}");
    tokio::time::sleep(std::time::Duration::from_millis(100)).await;
    println!("Connection closed");
    Ok(())
}

pub async fn interactive_client(host: &str, port: u16, tls: Option<TlsConnector>) -> Result<()> {
    let addr = format!("{host}:{port}");
    println!("Connecting to {addr}...");
    let mut tls_stream = if let Some(connector) = tls {
        let domain = rustls::pki_types::ServerName::try_from(host.to_string())
            .map_err(|_| anyhow::anyhow!("invalid server name"))?;
        let stream = TcpStream::connect(&addr).await?;
        Some(connector.connect(domain, stream).await?)
    } else {
        None
    };
    let mut plain_stream = if tls_stream.is_none() {
        Some(TcpStream::connect(&addr).await?)
    } else {
        None
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
        if let Some(s) = tls_stream.as_mut() {
            s.write_all(&packet).await?;
            s.flush().await?;
        } else if let Some(s) = plain_stream.as_mut() {
            s.write_all(&packet).await?;
            s.flush().await?;
        }
        println!("Sent: cmd_id={cmd_id}, data={data_s:?}");
    }
    println!("Disconnected");
    Ok(())
}

pub fn build_tls_client(cert_path: Option<&str>) -> Result<TlsConnector> {
    let config = if let Some(path) = cert_path {
        let mut root_store = tokio_rustls::rustls::RootCertStore::empty();
        for cert in load_certs(path)? {
            root_store.add(cert).context("add CA cert")?;
        }
        tokio_rustls::rustls::ClientConfig::builder()
            .with_root_certificates(root_store)
            .with_no_client_auth()
    } else {
        tokio_rustls::rustls::ClientConfig::builder()
            .dangerous()
            .with_custom_certificate_verifier(Arc::new(NoVerifier))
            .with_no_client_auth()
    };
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
    rustls_pemfile::certs(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .context("parse certs")
}

fn load_private_key(path: &str) -> Result<PrivateKeyDer<'static>> {
    let file = std::fs::File::open(path).with_context(|| format!("open {path}"))?;
    let mut reader = std::io::BufReader::new(file);
    rustls_pemfile::private_key(&mut reader)?
        .context("no private key found")
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
    crate::protocol::cleanup_old_nonces(&mut guard, now);
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

#[derive(Debug)]
struct NoVerifier;

impl rustls::client::danger::ServerCertVerifier for NoVerifier {
    fn verify_server_cert(
        &self,
        _end_entity: &CertificateDer<'_>,
        _intermediates: &[CertificateDer<'_>],
        _server_name: &rustls::pki_types::ServerName<'_>,
        _ocsp_response: &[u8],
        _now: rustls::pki_types::UnixTime,
    ) -> Result<rustls::client::danger::ServerCertVerified, rustls::Error> {
        Ok(rustls::client::danger::ServerCertVerified::assertion())
    }

    fn verify_tls12_signature(
        &self,
        _message: &[u8],
        _cert: &CertificateDer<'_>,
        _dss: &rustls::DigitallySignedStruct,
    ) -> Result<rustls::client::danger::HandshakeSignatureValid, rustls::Error> {
        Ok(rustls::client::danger::HandshakeSignatureValid::assertion())
    }

    fn verify_tls13_signature(
        &self,
        _message: &[u8],
        _cert: &CertificateDer<'_>,
        _dss: &rustls::DigitallySignedStruct,
    ) -> Result<rustls::client::danger::HandshakeSignatureValid, rustls::Error> {
        Ok(rustls::client::danger::HandshakeSignatureValid::assertion())
    }

    fn supported_verify_schemes(&self) -> Vec<rustls::SignatureScheme> {
        rustls::crypto::ring::default_provider()
            .signature_verification_algorithms
            .supported_schemes()
    }
}
