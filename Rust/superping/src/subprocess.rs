use std::time::Duration;

use regex::Regex;
use tokio::process::Command;
use tokio::time::timeout;

use crate::models::PingReply;

pub async fn subprocess_ping(
    host: &str,
    timeout_s: f64,
) -> Result<Vec<PingReply>, String> {
    let wait_for = Duration::from_secs_f64(timeout_s + 2.0);
    let args = ping_args(host, timeout_s);
    let (code, output) = run_command("ping", &args, wait_for).await?;

    let replies = parse_ping_output(&output);
    if replies.is_empty() && code != 0 {
        return Err(if output.trim().is_empty() {
            format!("ping exited with code {code}")
        } else {
            output.trim().to_string()
        });
    }

    Ok(replies)
}

async fn run_command(
    command: &str,
    args: &[String],
    wait_for: Duration,
) -> Result<(i32, String), String> {
    let mut process = Command::new(command);
    process.args(args);
    process.kill_on_drop(true);

    let output = timeout(wait_for, process.output())
        .await
        .map_err(|_| format!("Timed out running {command}"))?
        .map_err(|error| format!("Failed to run {command}: {error}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let combined = if stdout.trim().is_empty() {
        stderr.to_string()
    } else if stderr.trim().is_empty() {
        stdout.to_string()
    } else {
        format!("{stdout}{stderr}")
    };

    Ok((output.status.code().unwrap_or(-1), combined))
}

fn ping_args(host: &str, timeout_s: f64) -> Vec<String> {
    if cfg!(windows) {
        vec![
            "-n".into(),
            "1".into(),
            "-w".into(),
            format!("{}", (timeout_s * 1000.0) as u64),
            host.into(),
        ]
    } else if cfg!(target_os = "macos") {
        vec![
            "-c".into(),
            "1".into(),
            "-W".into(),
            format!("{}", (timeout_s * 1000.0) as u64),
            host.into(),
        ]
    } else {
        let wait_seconds = timeout_s.max(1.0).ceil() as u64;
        vec![
            "-c".into(),
            "1".into(),
            "-W".into(),
            wait_seconds.to_string(),
            host.into(),
        ]
    }
}

pub fn parse_ping_output(output: &str) -> Vec<PingReply> {
    let mut replies = Vec::new();
    let mut seq = 0u32;

    for line in output.lines() {
        let lower = line.to_ascii_lowercase();
        if lower.contains("request timed out")
            || lower.contains("no answer")
            || lower.contains("100% packet loss")
            || lower.contains("transmit failed")
        {
            seq += 1;
            replies.push(PingReply {
                seq,
                rtt_ms: 0.0,
                ttl: None,
                timed_out: true,
            });
            continue;
        }

        if let Some((rtt_ms, ttl)) = parse_reply_line(line) {
            seq += 1;
            replies.push(PingReply {
                seq,
                rtt_ms,
                ttl,
                timed_out: false,
            });
        }
    }

    replies
}

fn parse_reply_line(line: &str) -> Option<(f64, Option<u8>)> {
    static RTT_RE: std::sync::OnceLock<Regex> = std::sync::OnceLock::new();
    static TTL_RE: std::sync::OnceLock<Regex> = std::sync::OnceLock::new();

    let rtt_re = RTT_RE.get_or_init(|| {
        Regex::new(r"(?i)time(?:=|<)([\d.]+)\s*ms").expect("valid rtt regex")
    });
    let ttl_re = TTL_RE.get_or_init(|| Regex::new(r"(?i)ttl=(\d+)").expect("valid ttl regex"));

    let rtt_ms = rtt_re
        .captures(line)
        .and_then(|caps| caps.get(1))
        .and_then(|value| value.as_str().parse::<f64>().ok())?;

    let ttl = ttl_re
        .captures(line)
        .and_then(|caps| caps.get(1))
        .and_then(|value| value.as_str().parse::<u8>().ok());

    Some((rtt_ms, ttl))
}

pub fn should_fallback_native_error(error: &str) -> bool {
    let lower = error.to_ascii_lowercase();
    lower.contains("permission")
        || lower.contains("denied")
        || lower.contains("operation not permitted")
        || lower.contains("access is denied")
        || lower.contains("requires elevation")
        || lower.contains("cap_net_raw")
        || lower.contains("raw socket")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_linux_reply() {
        let output = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=12.3 ms";
        let replies = parse_ping_output(output);
        assert_eq!(replies.len(), 1);
        assert!((replies[0].rtt_ms - 12.3).abs() < f64::EPSILON);
        assert_eq!(replies[0].ttl, Some(117));
    }

    #[test]
    fn parses_windows_reply() {
        let output = "Reply from 8.8.8.8: bytes=32 time=14ms TTL=117";
        let replies = parse_ping_output(output);
        assert_eq!(replies.len(), 1);
        assert!((replies[0].rtt_ms - 14.0).abs() < f64::EPSILON);
        assert_eq!(replies[0].ttl, Some(117));
    }

    #[test]
    fn parses_timeout_line() {
        let output = "Request timed out.";
        let replies = parse_ping_output(output);
        assert_eq!(replies.len(), 1);
        assert!(replies[0].timed_out);
    }

    #[test]
    fn detects_permission_errors() {
        assert!(should_fallback_native_error(
            "Operation not permitted (os error 1)"
        ));
        assert!(!should_fallback_native_error("host unreachable"));
    }
}
