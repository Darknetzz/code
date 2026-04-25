import argparse
import json
import sys
from typing import Optional
from urllib import parse

import requests

DEFAULT_API_KEY = "YOUR_API_KEY"
DEFAULT_HEADERS = {
    "Content-Type": "application/json; charset=utf8",
    "User-Agent": "api_query",
}


def parse_headers(raw_headers: Optional[str], api_key: str) -> dict[str, str]:
    headers = dict(DEFAULT_HEADERS)
    if raw_headers:
        try:
            loaded = json.loads(raw_headers)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--headers must be valid JSON: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError("--headers JSON must be an object")
        headers.update({str(key): str(value) for key, value in loaded.items()})
    if api_key != DEFAULT_API_KEY:
        headers.setdefault("apikey", api_key)
    return headers


def parse_basic_args(raw_args: str, *, delimiter: str, separator: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not raw_args:
        return parsed
    for item in raw_args.split(delimiter):
        if not item:
            continue
        if separator not in item:
            raise ValueError(f"Argument {item!r} is missing separator {separator!r}")
        key, value = item.split(separator, 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Argument {item!r} has an empty key")
        parsed[key] = value.strip()
    return parsed


def parse_api_args(raw_args: str, args_format: str, *, delimiter: str, separator: str) -> dict:
    if not raw_args:
        return {}
    if args_format == "json":
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--args must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("--args JSON must be an object")
        return parsed
    return parse_basic_args(raw_args, delimiter=delimiter, separator=separator)


def curl(
    url: str,
    method: str,
    data: dict,
    headers: dict,
    *,
    timeout: int,
    verify_tls: bool,
    verbose: bool,
) -> requests.Response:
    if verbose:
        print(f"[VERBOSE] HEADERS: {headers}", file=sys.stderr)
        print(f"[VERBOSE] DATA: {data}", file=sys.stderr)
    response = requests.request(
        method=method.upper(),
        url=url,
        params=data,
        headers=headers,
        allow_redirects=True,
        stream=False,
        timeout=timeout,
        verify=verify_tls,
    )
    if verbose:
        print(f"[VERBOSE] RESPONSE: {response}", file=sys.stderr)
    return response


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__file__,
        description="Queries any API and returns the response body.",
        epilog="To simplify your everyday life :)",
    )
    parser.add_argument("endpoint", help="The full URL to the endpoint")
    parser.add_argument("-k", "--apikey", help="Your secret API key", default=DEFAULT_API_KEY)
    parser.add_argument("-m", "--method", help="HTTP method to use", default="GET")
    parser.add_argument("-a", "--args", help="Arguments to pass to the API", default="")
    parser.add_argument("--args-format", default="basic", choices=["basic", "json"])
    parser.add_argument("--headers", help="Request headers as a JSON object")
    parser.add_argument("--delim", help="Parameter delimiter for basic args", default=",")
    parser.add_argument("--equal", help="Key/value separator for basic args", default="=")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        headers = parse_headers(args.headers, args.apikey)
        api_args = parse_api_args(args.args, args.args_format, delimiter=args.delim, separator=args.equal)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.apikey != DEFAULT_API_KEY:
        api_args.setdefault("apikey", args.apikey)

    parsed_url = parse.urlsplit(args.endpoint)
    api_args.update(dict(parse.parse_qsl(parsed_url.query)))
    clean_url = parse.urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", parsed_url.fragment))

    response = curl(
        url=clean_url,
        method=args.method,
        data=api_args,
        headers=headers,
        timeout=args.timeout,
        verify_tls=not args.insecure,
        verbose=args.verbose,
    )
    print(response.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())