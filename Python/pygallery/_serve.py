"""Local static file server with HTTP Range support (needed for video seeking)."""

from __future__ import annotations

import os
import re
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_BIND = "0.0.0.0"
DEFAULT_PORT = 18923

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class RangeRequestHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        if not os.path.isfile(path):
            self.send_error(404, "File not found")
            return None

        ctype = self.guess_type(path)
        try:
            file_size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        range_header = self.headers.get("Range")
        if not range_header:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Last-Modified", self.date_time_string(int(mtime)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.start = 0
            self.end = file_size
            return f

        match = RANGE_RE.fullmatch(range_header.strip())
        if not match:
            f.close()
            self.send_error(400, "Invalid Range")
            return None

        start_s, end_s = match.groups()
        if start_s == "" and end_s == "":
            f.close()
            self.send_error(400, "Invalid Range")
            return None

        if start_s == "":
            suffix = int(end_s)
            if suffix <= 0:
                f.close()
                self.send_error(400, "Invalid Range")
                return None
            start = max(file_size - suffix, 0)
            end = file_size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else file_size - 1

        if start >= file_size or start < 0 or end < start:
            f.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            return None

        end = min(end, file_size - 1)
        length = end - start + 1

        self.send_response(206)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", self.date_time_string(int(mtime)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.start = start
        self.end = end + 1
        return f

    def copyfile(self, source, outputfile):
        start = getattr(self, "start", None)
        end = getattr(self, "end", None)
        if start is None or end is None:
            return super().copyfile(source, outputfile)

        source.seek(start)
        remaining = end - start
        bufsize = 64 * 1024
        while remaining > 0:
            chunk = source.read(min(bufsize, remaining))
            if not chunk:
                break
            try:
                outputfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                break
            remaining -= len(chunk)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def guess_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def serve_directory(
    directory: Path,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    open_path: str = "gallery.html",
) -> int:
    """Serve ``directory`` forever (Ctrl+C to stop). Returns process exit code."""
    directory = directory.resolve()
    if not directory.is_dir():
        print(f"Not a directory: {directory}", file=sys.stderr)
        return 1

    os.chdir(directory)
    try:
        server = ThreadingHTTPServer((bind, port), RangeRequestHandler)
    except OSError as exc:
        print(
            f"Could not bind {bind}:{port}: {exc}\n"
            f"Tip: another process may be using that port "
            f"(e.g. `ss -tlnp | grep {port}`), or pass --port N.",
            file=sys.stderr,
        )
        return 1

    page = open_path.lstrip("/")
    host_for_local = "127.0.0.1" if bind in ("0.0.0.0", "::") else bind
    print(f"Serving {directory}", flush=True)
    print(f"Local:  http://{host_for_local}:{port}/{page}", flush=True)
    if bind in ("0.0.0.0", "::"):
        lan = guess_lan_ip()
        if lan:
            print(f"LAN:    http://{lan}:{port}/{page}", flush=True)
    print("Press Ctrl+C to stop.\n", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        server.server_close()
    return 0
