#!/usr/bin/env python3
"""
Lab Hop Protocol (LHP) Client

Connect to an LHP server and send commands.
"""

import asyncio
import ssl
import sys
from protocol import LHPProtocol


async def send_packet(host, port, cmd_id, data, use_tls=False, certfile=None):
    """
    Connect to server and send a packet.
    
    Args:
        host: Server hostname or IP
        port: Server port
        cmd_id: Command ID (byte value, 0-255)
        data: Payload data (bytes or string)
        use_tls: Enable TLS encryption
        certfile: Path to SSL certificate file (for TLS verification)
    """
    # Convert string to bytes if needed
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    # Create packet using the protocol's static method
    packet = LHPProtocol.create_packet(cmd_id, data)
    
    # Create SSL context if needed
    ssl_context = None
    if use_tls:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False  # For self-signed certs
        ssl_context.verify_mode = ssl.CERT_NONE  # For self-signed certs
        if certfile:
            ssl_context.load_verify_locations(certfile)
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
    
    try:
        print(f"Connecting to {host}:{port}...")
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_context),
            timeout=10.0
        )
        print(f"✓ Connected to {host}:{port}")
        
        # Send the packet
        writer.write(packet)
        await writer.drain()
        print(f"✓ Sent packet: cmd_id={cmd_id}, payload={data!r}")
        
        # Wait a moment for any response (server doesn't send responses in current implementation)
        await asyncio.sleep(0.1)
        
        writer.close()
        await writer.wait_closed()
        print("✓ Connection closed")
        
    except asyncio.TimeoutError:
        print(f"✗ Connection timeout - server may be unreachable")
        sys.exit(1)
    except ConnectionRefusedError:
        print(f"✗ Connection refused - is the server running on {host}:{port}?")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


async def interactive_client(host, port, use_tls=False, certfile=None):
    """
    Interactive client that allows sending multiple commands.
    """
    ssl_context = None
    if use_tls:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        if certfile:
            ssl_context.load_verify_locations(certfile)
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
    
    try:
        print(f"Connecting to {host}:{port}...")
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_context),
            timeout=10.0
        )
        print(f"✓ Connected to {host}:{port}")
        print("Enter commands in format: <cmd_id> <data>")
        print("Example: 1 Hello World")
        print("Example: 2 reboot")
        print("Type 'quit' or 'exit' to disconnect\n")
        
        while True:
            try:
                command = input("> ").strip()
                if command.lower() in ('quit', 'exit', 'q'):
                    break
                
                if not command:
                    continue
                
                parts = command.split(' ', 1)
                if len(parts) == 1:
                    cmd_id = int(parts[0])
                    data = b''
                else:
                    cmd_id = int(parts[0])
                    data = parts[1].encode('utf-8')
                
                if cmd_id < 0 or cmd_id > 255:
                    print("Error: cmd_id must be 0-255")
                    continue
                
                packet = LHPProtocol.create_packet(cmd_id, data)
                writer.write(packet)
                await writer.drain()
                print(f"✓ Sent: cmd_id={cmd_id}, data={data!r}")
                
            except ValueError:
                print("Error: Invalid format. Use: <cmd_id> <data> (cmd_id must be a number)")
            except KeyboardInterrupt:
                break
        
        writer.close()
        await writer.wait_closed()
        print("\n✓ Disconnected")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Lab Hop Protocol (LHP) Client - Connect to LHP server and send commands"
    )
    parser.add_argument(
        "host",
        type=str,
        help="Server hostname or IP address"
    )
    parser.add_argument(
        "port",
        type=int,
        help="Server port"
    )
    parser.add_argument(
        "--tls",
        action="store_true",
        help="Enable TLS encryption"
    )
    parser.add_argument(
        "--certfile",
        type=str,
        help="Path to SSL certificate file (for TLS verification)"
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode (send multiple commands)"
    )
    parser.add_argument(
        "--cmd",
        type=int,
        help="Command ID to send (0-255). Use with --data"
    )
    parser.add_argument(
        "--data",
        type=str,
        help="Payload data to send (use with --cmd)"
    )
    
    args = parser.parse_args()
    
    if args.cmd is not None and args.interactive:
        parser.error("Cannot use --cmd/--data with --interactive")
    
    if args.cmd is not None and args.data is None:
        args.data = ""  # Empty payload
    
    if args.interactive:
        asyncio.run(interactive_client(
            args.host,
            args.port,
            use_tls=args.tls,
            certfile=args.certfile
        ))
    elif args.cmd is not None:
        asyncio.run(send_packet(
            args.host,
            args.port,
            args.cmd,
            args.data or "",
            use_tls=args.tls,
            certfile=args.certfile
        ))
    else:
        parser.print_help()
        print("\nExamples:")
        print("  # Interactive mode:")
        print("  python client.py localhost 8888 --interactive")
        print("  python client.py localhost 8888 -i")
        print("\n  # Send single command:")
        print("  python client.py localhost 8888 --cmd 1 --data 'Hello World'")
        print("  python client.py localhost 8888 --cmd 2 --data 'reboot'")
        print("\n  # With TLS:")
        print("  python client.py localhost 8888 --tls --interactive")
        sys.exit(1)
