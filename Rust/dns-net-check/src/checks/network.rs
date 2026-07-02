use std::time::Instant;

use reqwest::Client;
use tokio::net::TcpStream;
use tokio::process::Command;
use tokio::time::{timeout, Duration};

use crate::models::{detail_f64, detail_str, details_map, CheckResult};

pub async fn check_tcp_connect(host: &str, port: u16, timeout_s: f64) -> CheckResult {
    let target = format!("{host}:{port}");
    let started = Instant::now();
    let connect = timeout(
        Duration::from_secs_f64(timeout_s),
        TcpStream::connect((host, port)),
    )
    .await;

    match connect {
        Ok(Ok(_)) => {
            let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
            let mut details = details_map();
            detail_f64("timeout_s", timeout_s, &mut details);
            CheckResult::pass("tcp_connect", target, elapsed_ms, details)
        }
        Ok(Err(error)) => {
            let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
            let mut details = details_map();
            detail_f64("timeout_s", timeout_s, &mut details);
            CheckResult::fail(
                "tcp_connect",
                target,
                Some(elapsed_ms),
                format!("TCP connect failed: {error}"),
                "Verify service is listening, host is reachable, and firewall allows traffic.",
                details,
            )
        }
        Err(_) => {
            let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
            let mut details = details_map();
            detail_f64("timeout_s", timeout_s, &mut details);
            CheckResult::fail(
                "tcp_connect",
                target,
                Some(elapsed_ms),
                format!("TCP connect timed out after {timeout_s}s."),
                "Verify service is listening, host is reachable, and firewall allows traffic.",
                details,
            )
        }
    }
}

pub async fn check_http(url: &str, expected_status: Option<u16>, timeout_s: f64) -> CheckResult {
    let client = match Client::builder()
        .timeout(Duration::from_secs_f64(timeout_s))
        .build()
    {
        Ok(client) => client,
        Err(error) => {
            return CheckResult::fail(
                "http_probe",
                url,
                None,
                format!("HTTP client setup failed: {error}"),
                "Verify TLS trust store and HTTP client configuration.",
                details_map(),
            );
        }
    };

    let started = Instant::now();
    let response = client.get(url).send().await;
    let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;

    let response = match response {
        Ok(response) => response,
        Err(error) => {
            let mut details = details_map();
            detail_f64("timeout_s", timeout_s, &mut details);
            return CheckResult::fail(
                "http_probe",
                url,
                Some(elapsed_ms),
                format!("HTTP request failed: {error}"),
                "Verify URL, DNS resolution, TLS trust, and upstream service health.",
                details,
            );
        }
    };

    let status_code = response.status().as_u16();
    let mut details = details_map();
    detail_f64("timeout_s", timeout_s, &mut details);
    details.insert("status_code".into(), status_code.into());

    if let Some(expected) = expected_status {
        if status_code != expected {
            details.insert("expected_status".into(), expected.into());
            return CheckResult::fail(
                "http_probe",
                url,
                Some(elapsed_ms),
                format!("Unexpected HTTP status {status_code}, expected {expected}."),
                "Check app route health and expected response status.",
                details,
            );
        }
        details.insert("expected_status".into(), expected.into());
    }

    CheckResult::pass("http_probe", url, elapsed_ms, details)
}

pub async fn check_ping(host: &str, timeout_s: f64) -> CheckResult {
    let started = Instant::now();
    let output = ping_command(host, timeout_s).await;
    let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;

    match output {
        Ok((code, stdout)) => {
            if code == 0 {
                let mut details = details_map();
                details.insert("return_code".into(), code.into());
                detail_str("stdout", stdout, &mut details);
                CheckResult::pass("ping", host, elapsed_ms, details)
            } else {
                let mut details = details_map();
                details.insert("return_code".into(), code.into());
                detail_str("stdout", stdout, &mut details);
                CheckResult::fail(
                    "ping",
                    host,
                    Some(elapsed_ms),
                    "Ping failed.",
                    "Host may be unreachable or ICMP may be blocked.",
                    details,
                )
            }
        }
        Err(error) => CheckResult::fail(
            "ping",
            host,
            None,
            format!("Ping command failed: {error}"),
            "Ensure ping is available on PATH and ICMP is permitted.",
            details_map(),
        ),
    }
}

async fn ping_command(host: &str, timeout_s: f64) -> std::io::Result<(i32, String)> {
    let mut command = if cfg!(windows) {
        let mut command = Command::new("ping");
        command.args([
            "-n",
            "1",
            "-w",
            &format!("{}", (timeout_s * 1000.0) as u64),
            host,
        ]);
        command
    } else if cfg!(target_os = "macos") {
        let mut command = Command::new("ping");
        command.args([
            "-c",
            "1",
            "-W",
            &format!("{}", (timeout_s * 1000.0) as u64),
            host,
        ]);
        command
    } else {
        let mut command = Command::new("ping");
        let wait_seconds = timeout_s.max(1.0).ceil() as u64;
        command.args(["-c", "1", "-W", &wait_seconds.to_string(), host]);
        command
    };

    let output = command.output().await?;
    let code = output.status.code().unwrap_or(-1);
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    Ok((code, stdout))
}
