#!/usr/bin/env python3
"""
Quick demonstration script for pyrat.
This script connects to a running CNC server and sends some commands.
"""

import socket
import json
import time
import sys

def send_json_line(sock: socket.socket, payload: dict) -> None:
    """Send a JSON message."""
    data = (json.dumps(payload) + "\n").encode("utf-8")
    sock.sendall(data)

def recv_json_line(sock: socket.socket) -> dict | None:
    """Receive a JSON message."""
    chunks = []
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

def main():
    print("=" * 60)
    print("pyrat Demonstration")
    print("=" * 60)
    print("\nThis script demonstrates the pyrat RAT protocol.")
    print("Make sure both cnc_server.py and rat.py are running!")
    print("\nPress Enter to continue...")
    input()
    
    # Connect to CNC server
    print("\n[1] Connecting to CNC server at 127.0.0.1:9001...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 9001))
        print("    ✓ Connected!")
    except ConnectionRefusedError:
        print("    ✗ Connection refused. Is cnc_server.py running?")
        return
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return
    
    # Wait a moment for any hello messages
    time.sleep(0.5)
    
    # Try to receive any messages (like hello from client)
    sock.settimeout(0.5)
    try:
        while True:
            msg = recv_json_line(sock)
            if msg:
                print(f"    Received: {json.dumps(msg, indent=2)}")
    except socket.timeout:
        pass
    
    print("\n[2] Note: This demo script connects to the server,")
    print("    but the actual commands should be sent via the CNC CLI.")
    print("\n    To interact with the RAT client, use the CNC server's")
    print("    interactive prompt. Example commands:")
    print("      - list          (list connected clients)")
    print("      - use 1         (select client #1)")
    print("      - pwd           (get current directory)")
    print("      - exec dir      (run 'dir' command on Windows)")
    print("      - exec ls        (run 'ls' command on Linux/Mac)")
    print("      - ping          (ping the client)")
    
    sock.close()
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()

