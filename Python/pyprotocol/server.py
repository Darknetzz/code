#!/usr/bin/env python3
"""
Lab Hop Protocol (LHP) Server

Start an LHP server that listens for connections and processes commands.
"""

import asyncio
import ssl
import typer

from protocol import LHPAsyncProtocol

app = typer.Typer(help="Lab Hop Protocol (LHP) Server with replay protection and TLS support")


async def _server_main(use_tls=False, certfile=None, keyfile=None, host='0.0.0.0', port=8888):
    """
    Start the LHP server.
    
    Args:
        use_tls: Enable TLS encryption
        certfile: Path to SSL certificate file (required if use_tls=True)
        keyfile: Path to SSL private key file (required if use_tls=True)
        host: Host to bind to (default: 0.0.0.0)
        port: Port to listen on (default: 8888)
    """
    loop = asyncio.get_running_loop()
    ssl_context = None
    
    if use_tls:
        if not certfile or not keyfile:
            raise ValueError("certfile and keyfile required when use_tls=True")
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile, keyfile)
        print(f"Starting server with TLS encryption on {host}:{port}...")
    else:
        print(f"Starting server without encryption (plaintext) on {host}:{port}...")
        print("⚠️  WARNING: NOT recommended for production!")
    
    server = await loop.create_server(lambda: LHPAsyncProtocol(), host, port, ssl=ssl_context)
    print(f"✓ Server listening on {host}:{port}")
    async with server:
        await server.serve_forever()


@app.command()
def main(
    tls: bool = typer.Option(False, "--tls", help="Enable TLS encryption (requires --certfile and --keyfile)"),
    certfile: str = typer.Option(None, "--certfile", help="Path to SSL certificate file (required with --tls)"),
    keyfile: str = typer.Option(None, "--keyfile", help="Path to SSL private key file (required with --tls)"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to (default: 0.0.0.0)"),
    port: int = typer.Option(8888, "--port", help="Port to listen on (default: 8888)"),
):
    """
    Start the LHP server.
    """
    if tls and (not certfile or not keyfile):
        typer.echo("Error: --certfile and --keyfile are required when --tls is used", err=True)
        raise typer.Exit(1)
    
    try:
        asyncio.run(_server_main(
            use_tls=tls,
            certfile=certfile,
            keyfile=keyfile,
            host=host,
            port=port
        ))
    except KeyboardInterrupt:
        print("\n✓ Server stopped")


if __name__ == "__main__":
    app()
