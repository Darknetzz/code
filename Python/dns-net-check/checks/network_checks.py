from __future__ import annotations

import socket
import subprocess
import time

import requests

from checks.models import CheckResult, CheckStatus


def _ok(
    name: str,
    target: str,
    latency_ms: float,
    details: dict[str, object],
) -> CheckResult:
    return CheckResult(
        name=name,
        target=target,
        status=CheckStatus.PASS,
        latency_ms=latency_ms,
        details=details,
    )


def _fail(
    name: str,
    target: str,
    latency_ms: float | None,
    error: str,
    hint: str,
    details: dict[str, object] | None = None,
) -> CheckResult:
    return CheckResult(
        name=name,
        target=target,
        status=CheckStatus.FAIL,
        latency_ms=latency_ms,
        details=details or {},
        error=error,
        hint=hint,
    )


def check_tcp_connect(host: str, port: int, timeout_s: float = 5.0) -> CheckResult:
    target = f"{host}:{port}"
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            elapsed_ms = (time.perf_counter() - started) * 1000
            return _ok("tcp_connect", target, elapsed_ms, {"timeout_s": timeout_s})
    except OSError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return _fail(
            "tcp_connect",
            target,
            elapsed_ms,
            f"TCP connect failed: {exc}",
            "Verify service is listening, host is reachable, and firewall allows traffic.",
            {"timeout_s": timeout_s},
        )


def check_http(
    url: str,
    expected_status: int | None = None,
    timeout_s: float = 5.0,
) -> CheckResult:
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=timeout_s)
        elapsed_ms = (time.perf_counter() - started) * 1000
    except requests.RequestException as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return _fail(
            "http_probe",
            url,
            elapsed_ms,
            f"HTTP request failed: {exc}",
            "Verify URL, DNS resolution, TLS trust, and upstream service health.",
            {"timeout_s": timeout_s},
        )

    details: dict[str, object] = {
        "status_code": response.status_code,
        "timeout_s": timeout_s,
    }
    if expected_status is not None and response.status_code != expected_status:
        return _fail(
            "http_probe",
            url,
            elapsed_ms,
            f"Unexpected HTTP status {response.status_code}, expected {expected_status}.",
            "Check app route health and expected response status.",
            {"expected_status": expected_status, **details},
        )
    if expected_status is not None:
        details["expected_status"] = expected_status

    return _ok("http_probe", url, elapsed_ms, details)


def check_ping(host: str, timeout_s: float = 2.0) -> CheckResult:
    # Uses system ping for broad compatibility without raw socket code.
    command = [
        "ping",
        "-n",
        "1",
        "-w",
        str(int(timeout_s * 1000)),
        host,
    ]
    started = time.perf_counter()
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        elapsed_ms = (time.perf_counter() - started) * 1000
    except OSError as exc:
        return _fail(
            "ping",
            host,
            None,
            f"Ping command failed: {exc}",
            "Ensure ping is available on PATH and ICMP is permitted.",
        )

    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        return _fail(
            "ping",
            host,
            elapsed_ms,
            "Ping failed.",
            "Host may be unreachable or ICMP may be blocked.",
            {"return_code": completed.returncode, "stdout": output},
        )

    return _ok(
        "ping",
        host,
        elapsed_ms,
        {"return_code": completed.returncode, "stdout": output},
    )

