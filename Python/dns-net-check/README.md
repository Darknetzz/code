# DNS Network Check

Python CLI tool to verify DNS and basic network connectivity for one or more targets.

## Features

- DNS checks: `A`, `AAAA`, `CNAME`, `PTR`, `DNSSEC` (enabled by default)
- Network checks: TCP connect, HTTP probe, optional ping
- Human-readable output and JSON output
- Deterministic exit codes for automation/CI

## Requirements

- Python 3.10+

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Quick start

Run with explicit targets:

```powershell
python dns_net_check.py --host example.com --port example.com:443 --url https://example.com --no-ping
```

Run with no config/flags (built-in baseline checks):

```powershell
python dns_net_check.py
```

Run with config:

```powershell
python dns_net_check.py --config config.example.yaml
```

Run with JSON output:

```powershell
python dns_net_check.py --config config.example.yaml --json
```

## CLI options

- `--config <path>`: YAML config file path
- `--host <hostname>`: host to test (repeatable)
- `--port <host:port>`: TCP target (repeatable)
- `--url <url>`: URL to probe (repeatable)
- `--timeout <seconds>`: default timeout (default: `5.0`)
- `--json`: emit JSON report
- `--no-ping`: disable ping checks
- `--dnssec`: force-enable DNSSEC checks for host targets
- `--no-dnssec`: disable DNSSEC checks for host targets
- `--nameserver <ip>`: custom DNS resolver

## Config format

Use `config.example.yaml` as a template. Main keys:

- `timeout_s`: default timeout used by checks
- `ping`: enable/disable ping checks globally
- `nameserver`: optional DNS resolver IP
- `dnssec`: global DNSSEC default (`true`/`false`, default: `true`)
- `hosts`: DNS-oriented checks per host
  - Per-host options include `dnssec: true` and optional `dnssec_require_ad: true`
- `tcp`: TCP connectivity targets
- `urls`: HTTP probe targets

## Exit codes

- `0`: all checks passed
- `1`: one or more checks failed
- `2`: runtime/config/argument error

If you run with no targets and no config, the tool automatically uses baseline checks against `example.com` (`A` lookup, DNSSEC, ping, TCP 443, HTTPS probe).
