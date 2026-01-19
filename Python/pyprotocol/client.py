#!/usr/bin/env python3
"""
Lab Hop Protocol (LHP) Client

Connect to an LHP server and send commands.
"""

import asyncio
import ssl
import sys
import typer
from protocol import LHPProtocol

app = typer.Typer(help="Lab Hop Protocol (LHP) Client - Connect to LHP server and send commands")


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


@app.command()
def main(
    host: str = typer.Argument(..., help="Server hostname or IP address"),
    port: int = typer.Argument(..., help="Server port"),
    tls: bool = typer.Option(False, "--tls", help="Enable TLS encryption"),
    certfile: str = typer.Option(None, "--certfile", help="Path to SSL certificate file (for TLS verification)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode (send multiple commands)"),
    cmd: int = typer.Option(None, "--cmd", help="Command ID to send (0-255). Use with --data"),
    data: str = typer.Option(None, "--data", help="Payload data to send (use with --cmd)"),
):
    """
    Connect to LHP server and send commands.
    
    Examples:
    
        # Interactive mode:
        python client.py localhost 8888 --interactive
        python client.py localhost 8888 -i
    
        # Send single command:
        python client.py localhost 8888 --cmd 1 --data "Hello World"
        python client.py localhost 8888 --cmd 2 --data "reboot"
    
        # With TLS:
        python client.py localhost 8888 --tls --interactive
    """
    if cmd is not None and interactive:
        typer.echo("Error: Cannot use --cmd/--data with --interactive", err=True)
        raise typer.Exit(1)
    
    if interactive:
        asyncio.run(interactive_client(
            host,
            port,
            use_tls=tls,
            certfile=certfile
        ))
    elif cmd is not None:
        asyncio.run(send_packet(
            host,
            port,
            cmd,
            data or "",
            use_tls=tls,
            certfile=certfile
        ))
    else:
        typer.echo("Error: Must specify either --interactive or --cmd", err=True)
        typer.echo("\nExamples:")
        typer.echo("  # Interactive mode:")
        typer.echo("  python client.py localhost 8888 --interactive")
        typer.echo("  python client.py localhost 8888 -i")
        typer.echo("\n  # Send single command:")
        typer.echo("  python client.py localhost 8888 --cmd 1 --data 'Hello World'")
        typer.echo("  python client.py localhost 8888 --cmd 2 --data 'reboot'")
        typer.echo("\n  # With TLS:")
        typer.echo("  python client.py localhost 8888 --tls --interactive")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
