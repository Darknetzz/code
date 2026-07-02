use std::net::IpAddr;

use serde::Serialize;
use serde_json::{Map, Value};

use crate::cli::ProbeModeArg;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ProbeMethod {
    NativeIcmp,
    SystemPing,
    Tcp,
}

impl ProbeMethod {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::NativeIcmp => "native_icmp",
            Self::SystemPing => "system_ping",
            Self::Tcp => "tcp",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProbeMode {
    Icmp,
    Tcp,
}

impl From<ProbeModeArg> for ProbeMode {
    fn from(value: ProbeModeArg) -> Self {
        match value {
            ProbeModeArg::Icmp => Self::Icmp,
            ProbeModeArg::Tcp => Self::Tcp,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct PingReply {
    pub seq: u32,
    pub rtt_ms: f64,
    pub ttl: Option<u8>,
    pub timed_out: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProbeStats {
    pub packets_sent: u32,
    pub packets_received: u32,
    pub packet_loss_pct: f64,
    pub min_ms: Option<f64>,
    pub avg_ms: Option<f64>,
    pub max_ms: Option<f64>,
    pub stddev_ms: Option<f64>,
    pub jitter_ms: Option<f64>,
}

impl ProbeStats {
    pub fn to_json(&self) -> Map<String, Value> {
        let mut map = Map::new();
        map.insert("packets_sent".into(), Value::from(self.packets_sent));
        map.insert("packets_received".into(), Value::from(self.packets_received));
        map.insert("packet_loss_pct".into(), Value::from(self.packet_loss_pct));
        if let Some(v) = self.min_ms {
            map.insert("min_ms".into(), Value::from(v));
        }
        if let Some(v) = self.avg_ms {
            map.insert("avg_ms".into(), Value::from(v));
        }
        if let Some(v) = self.max_ms {
            map.insert("max_ms".into(), Value::from(v));
        }
        if let Some(v) = self.stddev_ms {
            map.insert("stddev_ms".into(), Value::from(v));
        }
        if let Some(v) = self.jitter_ms {
            map.insert("jitter_ms".into(), Value::from(v));
        }
        map
    }
}

#[derive(Debug, Clone)]
pub struct ResolvedHost {
    pub name: String,
    pub ip: IpAddr,
    pub ptr_name: Option<String>,
    pub port: Option<u16>,
}

#[derive(Debug, Clone)]
pub struct HostProbeResult {
    pub name: String,
    pub resolved_ip: String,
    pub port: Option<u16>,
    pub ptr_name: Option<String>,
    pub method: ProbeMethod,
    pub stats: ProbeStats,
    pub replies: Vec<PingReply>,
    pub interrupted: bool,
    pub error: Option<String>,
}

impl HostProbeResult {
    pub fn ok(&self) -> bool {
        self.stats.packets_received > 0
    }

    pub fn to_json(&self) -> Map<String, Value> {
        let mut map = Map::new();
        map.insert("name".into(), Value::String(self.name.clone()));
        map.insert("resolved_ip".into(), Value::String(self.resolved_ip.clone()));
        if let Some(port) = self.port {
            map.insert("port".into(), Value::from(port));
        }
        if let Some(ptr) = &self.ptr_name {
            map.insert("ptr".into(), Value::String(ptr.clone()));
        }
        map.insert(
            "method".into(),
            Value::String(self.method.as_str().into()),
        );
        map.insert("ok".into(), Value::Bool(self.ok()));
        map.insert("stats".into(), Value::Object(self.stats.to_json()));
        map.insert(
            "replies".into(),
            Value::Array(
                self.replies
                    .iter()
                    .map(|reply| {
                        let mut item = Map::new();
                        item.insert("seq".into(), Value::from(reply.seq));
                        item.insert("rtt_ms".into(), Value::from(reply.rtt_ms));
                        if let Some(ttl) = reply.ttl {
                            item.insert("ttl".into(), Value::from(ttl));
                        }
                        item.insert("timed_out".into(), Value::Bool(reply.timed_out));
                        Value::Object(item)
                    })
                    .collect(),
            ),
        );
        map.insert("interrupted".into(), Value::Bool(self.interrupted));
        if let Some(error) = &self.error {
            map.insert("error".into(), Value::String(error.clone()));
        }
        map
    }
}
