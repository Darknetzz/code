use std::time::{Duration, Instant};

use tokio::net::TcpStream;
use tokio::time::timeout;

use crate::models::PingReply;

pub async fn tcp_probe(
    host: &str,
    port: u16,
    seq: u32,
    timeout_s: f64,
) -> PingReply {
    let started = Instant::now();
    let connect = timeout(
        Duration::from_secs_f64(timeout_s),
        TcpStream::connect((host, port)),
    )
    .await;

    match connect {
        Ok(Ok(_)) => PingReply {
            seq,
            rtt_ms: started.elapsed().as_secs_f64() * 1000.0,
            ttl: None,
            timed_out: false,
        },
        Ok(Err(_)) | Err(_) => PingReply {
            seq,
            rtt_ms: started.elapsed().as_secs_f64() * 1000.0,
            ttl: None,
            timed_out: true,
        },
    }
}
