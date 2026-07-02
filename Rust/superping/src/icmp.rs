use std::net::IpAddr;
use std::sync::Arc;
use std::time::Duration;

use surge_ping::{Client, Config, IcmpPacket, PingIdentifier, PingSequence};

use crate::models::PingReply;

pub struct NativeIcmpClient {
    client: Arc<Client>,
    payload: Vec<u8>,
}

impl NativeIcmpClient {
    pub fn new(payload_size: usize, ttl: Option<u8>) -> Result<Self, String> {
        let mut builder = Config::builder();
        if let Some(ttl_value) = ttl {
            builder = builder.ttl(u32::from(ttl_value));
        }
        let config = builder.build();
        let client = Client::new(&config).map_err(|error| error.to_string())?;
        let payload = vec![0u8; payload_size.max(8)];
        Ok(Self {
            client: Arc::new(client),
            payload,
        })
    }

    pub async fn ping_once(
        &self,
        host: IpAddr,
        seq: u32,
        timeout_s: f64,
    ) -> Result<PingReply, String> {
        let ident = PingIdentifier::from(std::process::id() as u16);
        let mut pinger = self.client.pinger(host, ident).await;
        pinger.timeout(Duration::from_secs_f64(timeout_s.max(0.1)));

        match pinger
            .ping(PingSequence::from(seq as u16), &self.payload)
            .await
        {
            Ok((packet, duration)) => {
                let ttl = extract_ttl(&packet);
                Ok(PingReply {
                    seq,
                    rtt_ms: duration.as_secs_f64() * 1000.0,
                    ttl,
                    timed_out: false,
                })
            }
            Err(error) => {
                let message = error.to_string();
                if message.to_ascii_lowercase().contains("timeout") {
                    Ok(PingReply {
                        seq,
                        rtt_ms: 0.0,
                        ttl: None,
                        timed_out: true,
                    })
                } else {
                    Err(message)
                }
            }
        }
    }
}

fn extract_ttl(packet: &IcmpPacket) -> Option<u8> {
    match packet {
        IcmpPacket::V4(packet) => packet.get_ttl(),
        IcmpPacket::V6(packet) => Some(packet.get_max_hop_limit()),
    }
}

pub fn is_permission_error(message: &str) -> bool {
    crate::subprocess::should_fallback_native_error(message)
}
