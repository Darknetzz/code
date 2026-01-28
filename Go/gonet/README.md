# gonet

Network CLI tools — DNS, whois, port check, ping, HTTP headers/download, static server, cert info, URL encode, JWT decode, public/local IP.

## Usage

```
gonet <command> [options] [args]
```

## Build

```bash
go build -o gonet .
```

## Commands

| Command        | Description |
|----------------|-------------|
| `dns`          | Resolve hostname to IPs or IP to PTR; optional `-mx`, `-txt` |
| `resolve`      | Simple A/AAAA lookup |
| `whois`        | Whois lookup (default server: whois.iana.org; use `-server` to override) |
| `ports`        | Check if TCP ports are open: `gonet ports host 80 443 22` |
| `ping`         | ICMP ping (`-c n`, `-6` for IPv6). May need admin on Windows. |
| `headers`      | Fetch URL, print status + headers; `-body`, `-H "Key: Val"`, `-X METHOD`, `-no-follow` |
| `download`     | Download URL; `-o file`, `-hash md5|sha256|sha512` |
| `serve`        | Static file server; `-port`, `-bind` |
| `proxy-headers`| Debug server that prints request method, URL, headers, body |
| `cert`         | TLS cert info for host:port (subject, issuer, expiry, SANs) |
| `urlencode`    | Encode or `-d` decode URL query segment (stdin or args) |
| `jwt-decode`   | Decode JWT payload (no verification) |
| `ip`, `myip`   | Show public and/or local IPs; `-public` or `-internal` for one only |

## Examples

```bash
gonet dns example.com
gonet dns -mx -txt example.com
gonet dns 8.8.8.8
gonet resolve api.github.com
gonet whois example.com
gonet ports google.com 80 443
gonet ping -c 4 8.8.8.8
gonet headers https://example.com
gonet download -o out.html -hash sha256 https://example.com
gonet serve -port 9000 .
gonet cert github.com:443
echo "hello world" | gonet urlencode
gonet jwt-decode "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
gonet ip
gonet ip -public
gonet ip -internal
```
