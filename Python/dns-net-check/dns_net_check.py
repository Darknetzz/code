from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from checks.dns_checks import check_cname, check_dns_record, check_dnssec, check_ptr
from checks.models import CheckResult, CheckStatus
from checks.network_checks import check_http, check_ping, check_tcp_connect

console = Console()
err_console = Console(stderr=True)

FALLBACK_TARGETS: dict[str, list[dict[str, Any]]] = {
    "hosts": [{"name": "example.com", "dns_records": ["A"]}],
    "tcp": [{"host": "example.com", "port": 443}],
    "urls": [{"url": "https://example.com", "expected_status": 200}],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DNS/network verification tool")
    parser.add_argument("--config", type=Path, help="Path to YAML config file.")
    parser.add_argument("--host", action="append", default=[], help="Host to test.")
    parser.add_argument(
        "--port",
        action="append",
        default=[],
        help="TCP target in host:port format (repeatable).",
    )
    parser.add_argument("--url", action="append", default=[], help="URL to probe.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Default timeout seconds.")
    parser.add_argument("--json", action="store_true", help="Output JSON report.")
    parser.add_argument("--no-ping", action="store_true", help="Skip ping checks.")
    parser.add_argument(
        "--dnssec",
        action="store_true",
        help="Force-enable DNSSEC check for each host target.",
    )
    parser.add_argument(
        "--no-dnssec",
        action="store_true",
        help="Disable DNSSEC checks for host targets.",
    )
    parser.add_argument(
        "--nameserver",
        default=None,
        help="Optional DNS resolver IP to use instead of system default.",
    )
    return parser.parse_args()


def _load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Config root must be a mapping/object.")
    return loaded


def _parse_port_targets(items: list[str]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for item in items:
        if ":" not in item:
            raise ValueError(f"Invalid --port value '{item}', expected host:port")
        host, raw_port = item.rsplit(":", 1)
        targets.append({"host": host, "port": int(raw_port)})
    return targets


def _normalize_hosts(config: dict[str, Any], cli_hosts: list[str]) -> list[dict[str, Any]]:
    configured = config.get("hosts", [])
    results: list[dict[str, Any]] = []
    if isinstance(configured, list):
        for item in configured:
            if isinstance(item, str):
                results.append({"name": item})
            elif isinstance(item, dict):
                results.append(item)
    for host in cli_hosts:
        results.append({"name": host})
    return results


def _normalize_tcp(config: dict[str, Any], cli_ports: list[str]) -> list[dict[str, Any]]:
    configured = config.get("tcp", [])
    results: list[dict[str, Any]] = configured if isinstance(configured, list) else []
    results.extend(_parse_port_targets(cli_ports))
    return results


def _normalize_urls(config: dict[str, Any], cli_urls: list[str]) -> list[dict[str, Any]]:
    configured = config.get("urls", [])
    results: list[dict[str, Any]] = []
    if isinstance(configured, list):
        for item in configured:
            if isinstance(item, str):
                results.append({"url": item})
            elif isinstance(item, dict):
                results.append(item)
    for url in cli_urls:
        results.append({"url": url})
    return results


def _has_any_targets(config: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.host or args.port or args.url:
        return True
    for key in ("hosts", "tcp", "urls"):
        values = config.get(key, [])
        if isinstance(values, list) and values:
            return True
    return False


def _with_fallback_targets(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if _has_any_targets(config, args):
        return config
    merged = dict(config)
    merged.update(FALLBACK_TARGETS)
    return merged


def run_checks(args: argparse.Namespace, config: dict[str, Any]) -> list[CheckResult]:
    timeout_s = float(config.get("timeout_s", args.timeout))
    do_ping = bool(config.get("ping", True)) and not args.no_ping
    default_dnssec = bool(config.get("dnssec", True))
    if args.no_dnssec:
        default_dnssec = False
    elif args.dnssec:
        default_dnssec = True
    nameserver = args.nameserver or config.get("nameserver")
    results: list[CheckResult] = []

    for host_cfg in _normalize_hosts(config, args.host):
        host = host_cfg.get("name")
        if not host:
            continue
        dns_records = host_cfg.get("dns_records", ["A"])
        for record_type in dns_records:
            expected = host_cfg.get("expected", {}).get(str(record_type).upper())
            if expected and not isinstance(expected, list):
                expected = [str(expected)]
            results.append(
                check_dns_record(
                    host=host,
                    record_type=str(record_type).upper(),
                    expected=expected,
                    timeout_s=timeout_s,
                    nameserver=nameserver,
                )
            )

        cname_expected = host_cfg.get("expected", {}).get("CNAME")
        if cname_expected is not None:
            results.append(
                check_cname(
                    host=host,
                    expected=str(cname_expected),
                    timeout_s=timeout_s,
                    nameserver=nameserver,
                )
            )

        if do_ping:
            results.append(check_ping(host=host, timeout_s=min(timeout_s, 5.0)))

        ptr_ip = host_cfg.get("ptr_ip")
        if ptr_ip:
            results.append(
                check_ptr(
                    ip=str(ptr_ip),
                    expected=host_cfg.get("expected", {}).get("PTR"),
                    timeout_s=timeout_s,
                    nameserver=nameserver,
                )
            )

        do_dnssec = bool(host_cfg.get("dnssec", default_dnssec))
        if do_dnssec:
            require_ad = bool(host_cfg.get("dnssec_require_ad", False))
            results.append(
                check_dnssec(
                    host=host,
                    timeout_s=timeout_s,
                    nameserver=nameserver,
                    require_ad=require_ad,
                )
            )

    for tcp_cfg in _normalize_tcp(config, args.port):
        host = str(tcp_cfg.get("host", "")).strip()
        port = tcp_cfg.get("port")
        if not host or port is None:
            continue
        results.append(check_tcp_connect(host=host, port=int(port), timeout_s=timeout_s))

    for url_cfg in _normalize_urls(config, args.url):
        url = str(url_cfg.get("url", "")).strip()
        if not url:
            continue
        expected_status = url_cfg.get("expected_status")
        results.append(
            check_http(url=url, expected_status=expected_status, timeout_s=timeout_s)
        )

    return results


def _status_style(status: CheckStatus) -> str:
    if status is CheckStatus.PASS:
        return "bold green"
    if status is CheckStatus.FAIL:
        return "bold red"
    return "bold yellow"


def _message_markup(result: CheckResult) -> str:
    if result.status is CheckStatus.PASS:
        return "[green]ok[/]"
    if result.error:
        return f"[red]{result.error}[/]"
    return "[red]failed[/]"


def print_human(results: list[CheckResult]) -> None:
    for result in results:
        status_label = result.status.value.upper()
        latency = f"{result.latency_ms:.1f}ms" if result.latency_ms is not None else "-"
        console.print(
            f"[{_status_style(result.status)}]{status_label}[/] "
            f"[cyan]{result.name}[/] "
            f"target=[white]{result.target}[/] "
            f"latency=[dim]{latency}[/] "
            f"msg={_message_markup(result)}"
        )
        if result.hint and result.status is CheckStatus.FAIL:
            console.print(f"  [dim]hint:[/] [italic]{result.hint}[/]")

    passed = sum(1 for result in results if result.status is CheckStatus.PASS)
    failed = sum(1 for result in results if result.status is CheckStatus.FAIL)
    warned = sum(1 for result in results if result.status is CheckStatus.WARN)
    console.print()
    console.print(
        "Summary: "
        f"[green]pass={passed}[/] "
        f"[red]fail={failed}[/] "
        f"[yellow]warn={warned}[/] "
        f"[bold]total={len(results)}[/]"
    )


def print_json(results: list[CheckResult]) -> None:
    payload = {
        "summary": {
            "pass": sum(1 for result in results if result.status is CheckStatus.PASS),
            "fail": sum(1 for result in results if result.status is CheckStatus.FAIL),
            "warn": sum(1 for result in results if result.status is CheckStatus.WARN),
            "total": len(results),
        },
        "results": [result.to_dict() for result in results],
    }
    print(json.dumps(payload, indent=2))


def main() -> int:
    try:
        args = parse_args()
        loaded_config = _load_config(args.config)
        using_fallback_targets = not _has_any_targets(loaded_config, args)
        config = _with_fallback_targets(loaded_config, args)
        results = run_checks(args, config)
    except Exception as exc:  # pragma: no cover - CLI fail-safe path
        err_console.print(f"[bold red]FAIL[/] Unable to run checks: {exc}")
        return 2

    if args.json:
        print_json(results)
    else:
        if using_fallback_targets:
            console.print("[dim]No targets supplied; running built-in baseline checks.[/]")
        print_human(results)

    return 1 if any(result.status is CheckStatus.FAIL for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

