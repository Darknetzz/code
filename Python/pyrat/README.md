## pyrat – Educational Remote Administration Tool

**pyrat** is a deliberately simple, educational Remote Administration Tool (RAT) and Command‑and‑Control (CNC) server pair, written in Python.  
It is designed to demonstrate basic client/server networking and JSON‑based protocols in a controlled lab environment.

> **WARNING / DISCLAIMER**  
> This software is provided **for educational and authorized testing purposes only**.  
> You must **not** use it on any system, device, or network that you do not own or do not have **explicit written permission** to test.  
> Misuse may violate computer misuse, privacy, and criminal laws in your jurisdiction.  
> The author(s) and contributors **assume no liability** for any misuse or damage caused by this software.

---

## Components

- **RAT client**: `rat.py`  
  Connects out to a CNC server and waits for JSON‑encoded commands.

- **CNC server**: `cnc_server.py`  
  Listens for incoming client connections and provides a simple interactive CLI to control them.

Communication is done over TCP, using **newline‑delimited JSON messages**.

---

## Protocol Overview

### Messages from client to CNC

- **`hello`**
  - Sent immediately after the client connects.
  - Example:
    ```json
    {
      "type": "hello",
      "hostname": "client-host",
      "cwd": "C:\\\\Users\\\\User",
      "platform": "win32",
      "pid": 1234
    }
    ```

- **`heartbeat`**
  - Sent periodically (about every 20 seconds) so the CNC can see that the client is still alive.
  - Example:
    ```json
    {
      "type": "heartbeat",
      "cwd": "C:\\\\Users\\\\User"
    }
    ```

- **`exec_result`**
  - Response to an `exec` command from the CNC.
  - Example:
    ```json
    {
      "type": "exec_result",
      "cmd": "dir",
      "cwd": "C:\\\\Users\\\\User",
      "result": {
        "ok": true,
        "stdout": "...\r\n",
        "stderr": "",
        "returncode": 0
      }
    }
    ```

- **`cd_result`**
  - Response to a `cd` command, indicating success/failure.

- **`pwd_result`**
  - Response to a `pwd` command, containing the current working directory.

- **`pong`**
  - Response to a `ping` message from the CNC.

- **`bye`**
  - Sent when the client receives an `exit` command and is about to terminate.

---

### Messages from CNC to client

- **`ping`**
  - Asks the client to respond with a `pong`.

- **`exec`**
  - Instructs the client to execute a shell command.
  - Example:
    ```json
    {
      "type": "exec",
      "cmd": "dir"
    }
    ```

- **`cd`**
  - Asks the client to change its working directory.

- **`pwd`**
  - Asks the client to report its current working directory.

- **`exit`**
  - Requests the client to shut down.

Unknown message types are rejected by the client with an `error` message.

---

## Configuration (`config.json`)

Both the RAT client and CNC server can read default settings from `config.json`
in the same directory:

```json
{
  "//": "Configuration for pyrat RAT client and CNC server. CLI flags override these values.",
  "server": {
    "host": "0.0.0.0",
    "port": 9001
  },
  "client": {
    "host": "127.0.0.1",
    "port": 9001,
    "reconnect_delay": 5.0,
    "heartbeat_interval": 20.0
  }
}
```

- **Server section** controls default bind host/port for `cnc_server.py`.
- **Client section** controls default CNC host/port and timing for `rat.py`.
- **Command‑line flags always override the config file** when explicitly provided.

---

## Running the CNC Server

On the **controlling** machine:

```bash
cd Python/pyrat
python cnc_server.py
```

You can still override config values explicitly:

```bash
python cnc_server.py --host 0.0.0.0 --port 9001
```

You should see something like:

```text
[cnc] Listening on 0.0.0.0:9001
```

The CNC server exposes a simple CLI:

- **`help`** – Show help and available commands.
- **`list`** – List connected clients with IDs and basic info.
- **`use <id>`** – Select a client to control (e.g. `use 1`).
- **`ping`** – Send a ping to the selected client.
- **`exec <cmd>`** – Execute a shell command on the selected client.
- **`cd <path>`** – Change working directory on the selected client.
- **`pwd`** – Ask the client for its current working directory.
- **`exit_client`** – Ask the selected client to exit.
- **`quit` / `exit` / `q`** – Quit the CNC server.

---

## Running the RAT Client

On the **authorized target** machine:

```bash
cd Python/pyrat
python rat.py
```

You can still override config values explicitly:

```bash
python rat.py --host <CNC_IP> --port 9001
```

Examples:

- Local testing on the same machine:
  ```bash
  python rat.py --host 127.0.0.1 --port 9001
  ```
- LAN testing when CNC is on another host, e.g. `192.168.1.10`:
  ```bash
  python rat.py --host 192.168.1.10 --port 9001
  ```

The client will:

- Attempt to connect to the CNC.
- Send a `hello` message on connect.
- Periodically send `heartbeat` messages.
- Listen for commands (`ping`, `exec`, `cd`, `pwd`, `exit`) and respond accordingly.
- Automatically attempt to reconnect if the CNC is unreachable (with a small delay).

---

## Educational Use Ideas

- Inspect and extend the JSON protocol (add new commands or metadata).
- Add simple authentication or pre‑shared keys to better understand secure design.
- Implement logging on both client and server sides.
- Add a very small GUI on top of `cnc_server.py` to observe multiple clients.

Remember: **always** keep experiments restricted to lab machines or systems where you have **explicit authorization**.


