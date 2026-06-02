from __future__ import annotations

import time

import dns.exception
import dns.flags
import dns.message
import dns.query
import dns.reversename
import dns.rdatatype
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


def check_dnssec(
    host: str,
    timeout_s: float = 5.0,
    nameserver: str | None = None,
    require_ad: bool = False,
) -> CheckResult:
    resolver = dns.resolver.Resolver(configure=True)
    resolver.lifetime = timeout_s
    resolver.timeout = timeout_s
    if nameserver:
        resolver.nameservers = [nameserver]

    active_nameserver = resolver.nameservers[0]
    query = dns.message.make_query(host, dns.rdatatype.DNSKEY, want_dnssec=True)
    started = time.perf_counter()
    try:
        response = dns.query.udp(query, active_nameserver, timeout=timeout_s)
        if response.flags & dns.flags.TC:
            response = dns.query.tcp(query, active_nameserver, timeout=timeout_s)
        elapsed_ms = (time.perf_counter() - started) * 1000
    except dns.exception.Timeout:
        return _fail(
            "dns_dnssec",
            host,
            None,
            f"DNSSEC query timed out after {timeout_s}s.",
            "Check resolver reachability and allow DNS traffic to the resolver.",
            {"nameserver": active_nameserver},
        )
    except dns.exception.DNSException as exc:
        return _fail(
            "dns_dnssec",
            host,
            None,
            f"DNSSEC query failed: {exc}",
            "Check resolver DNSSEC support and zone DNSSEC configuration.",
            {"nameserver": active_nameserver},
        )

    has_dnskey = any(rrset.rdtype == dns.rdatatype.DNSKEY for rrset in response.answer)
    has_rrsig = any(rrset.rdtype == dns.rdatatype.RRSIG for rrset in response.answer)
    ad_flag = bool(response.flags & dns.flags.AD)
    details = {
        "nameserver": active_nameserver,
        "dnskey_present": has_dnskey,
        "rrsig_present": has_rrsig,
        "ad_flag": ad_flag,
    }

    if not has_dnskey:
        return _fail(
            "dns_dnssec",
            host,
            elapsed_ms,
            "DNSKEY record not present in answer.",
            "Ensure the zone is DNSSEC-signed and DNSKEY records are published.",
            details=details,
        )
    if not has_rrsig:
        return _fail(
            "dns_dnssec",
            host,
            elapsed_ms,
            "RRSIG record not present in answer.",
            "Ensure signatures are generated and published for DNSKEY RRset.",
            details=details,
        )
    if require_ad and not ad_flag:
        return _fail(
            "dns_dnssec",
            host,
            elapsed_ms,
            "AD (Authenticated Data) flag not set by resolver.",
            "Use a validating resolver or disable strict AD requirement.",
            details=details,
        )

    return _ok("dns_dnssec", host, elapsed_ms, details)

