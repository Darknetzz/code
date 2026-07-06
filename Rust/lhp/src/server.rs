use std::sync::{Arc, Mutex};

use anyhow::Result;
use tokio::io::AsyncReadExt;
use tokio::net::TcpListener;

use crate::protocol::{parse_packet, HEADER_SIZE, STX};
use crate::validate_packet;

pub async fn run_server(
    host: &str,
    port: u16,
    tls: Option<tokio_rustls::TlsAcceptor>,
) -> Result<()> {
    let addr = format!("{host}:{port}");
    let listener = TcpListener::bind(&addr).await?;
    if tls.is_some() {
        println!("Starting server with TLS on {addr}...");
    } else {
        println!("Starting server without encryption on {addr}...");
        println!("WARNING: NOT recommended for production!");
    }
    println!("Server listening on {addr}");
    let seen = Arc::new(Mutex::new(std::collections::HashSet::new()));
    loop {
        let (stream, peer) = listener.accept().await?;
        println!("Connection from {peer}");
        let seen = Arc::clone(&seen);
        let tls_acceptor = tls.clone();
        tokio::spawn(async move {
            if let Some(acceptor) = tls_acceptor {
                match acceptor.accept(stream).await {
                    Ok(tls_stream) => handle_connection(Box::pin(tls_stream), seen).await,
                    Err(e) => eprintln!("TLS handshake failed: {e}"),
                }
            } else {
                handle_connection(Box::pin(stream), seen).await;
            }
        });
    }
}

async fn handle_connection(
    mut stream: std::pin::Pin<Box<dyn tokio::io::AsyncRead + tokio::io::AsyncWrite + Send>>,
    seen: Arc<Mutex<std::collections::HashSet<u32>>>,
) {
    let mut buffer = Vec::new();
    let mut read_buf = [0u8; 4096];
    loop {
        match stream.read(&mut read_buf).await {
            Ok(0) => break,
            Ok(n) => buffer.extend_from_slice(&read_buf[..n]),
            Err(e) => {
                eprintln!("read error: {e}");
                break;
            }
        }
        while buffer.len() >= HEADER_SIZE {
            if buffer[0] != STX {
                buffer.remove(0);
                continue;
            }
            let payload_len = u16::from_be_bytes([buffer[1], buffer[2]]) as usize;
            let total = HEADER_SIZE + payload_len + 1;
            if buffer.len() < total {
                break;
            }
            let packet_bytes: Vec<u8> = buffer.drain(..total).collect();
            if let Some(packet) = parse_packet(&packet_bytes) {
                if validate_packet(&packet, &seen) {
                    let text = String::from_utf8_lossy(&packet.payload);
                    println!("Received Command {}: {text}", packet.cmd_id);
                }
            }
        }
    }
}
