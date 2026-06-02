from __future__ import annotations

import time

import dns.exception
import dns.reversename
import dns.resolver

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


def _resolve_with_timing(
    host_or_name: str,
    record_type: str,
    timeout_s: float,
    nameserver: str | None = None,
) -> tuple[list[str], float]:
    resolver = dns.resolver.Resolver(configure=True)
    resolver.lifetime = timeout_s
    resolver.timeout = timeout_s
    if nameserver:
        resolver.nameservers = [nameserver]

    started = time.perf_counter()
    answers = resolver.resolve(host_or_name, record_type)
    elapsed_ms = (time.perf_counter() - started) * 1000
    values = [answer.to_text().rstrip(".") for answer in answers]
    return values, elapsed_ms


def check_dns_record(
    host: str,
    record_type: str = "A",
    expected: list[str] | None = None,
    timeout_s: float = 5.0,
    nameserver: str | None = None,
) -> CheckResult:
    check_name = f"dns_{record_type.lower()}"
    try:
        values, elapsed_ms = _resolve_with_timing(host, record_type, timeout_s, nameserver)
    except dns.resolver.NXDOMAIN:
        return _fail(
            check_name,
            host,
            None,
            f"{host} does not exist (NXDOMAIN).",
            "Verify the hostname spelling and DNS zone configuration.",
        )
    except dns.resolver.NoAnswer:
        return _fail(
            check_name,
            host,
            None,
            f"No {record_type} answer for {host}.",
            "Verify the expected record type exists for this host.",
        )
    except dns.exception.Timeout:
        return _fail(
            check_name,
            host,
            None,
            f"DNS query timed out after {timeout_s}s.",
            "Check resolver reachability and firewall/network policies.",
        )
    except dns.exception.DNSException as exc:
        return _fail(
            check_name,
            host,
            None,
            f"DNS query failed: {exc}",
            "Check DNS resolver health and request format.",
        )

    details: dict[str, object] = {"record_type": record_type, "values": values}
    if expected:
        expected_set = {item.rstrip(".") for item in expected}
        value_set = set(values)
        if not expected_set.issubset(value_set):
            return _fail(
                check_name,
                host,
                elapsed_ms,
                "Resolved records do not match expected values.",
                "Update DNS records or expected values in config.",
                details={"expected": sorted(expected_set), **details},
            )
        details["expected"] = sorted(expected_set)

    return _ok(check_name, host, elapsed_ms, details)


def check_cname(
    host: str,
    expected: str | None = None,
    timeout_s: float = 5.0,
    nameserver: str | None = None,
) -> CheckResult:
    result = check_dns_record(
        host=host,
        record_type="CNAME",
        expected=[expected] if expected else None,
        timeout_s=timeout_s,
        nameserver=nameserver,
    )
    result.name = "dns_cname"
    return result


def check_ptr(
    ip: str,
    expected: str | None = None,
    timeout_s: float = 5.0,
    nameserver: str | None = None,
) -> CheckResult:
    reverse_name = dns.reversename.from_address(ip).to_text()
    result = check_dns_record(
        host=reverse_name,
        record_type="PTR",
        expected=[expected] if expected else None,
        timeout_s=timeout_s,
        nameserver=nameserver,
    )
    result.name = "dns_ptr"
    result.target = ip
    if result.status is CheckStatus.PASS:
        result.details["reverse_name"] = reverse_name
    return result

