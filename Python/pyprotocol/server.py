#!/usr/bin/env python3
"""
Lab Hop Protocol (LHP) Server

Start an LHP server that listens for connections and processes commands.
"""

import argparse
import asyncio
import ssl

from protocol import LHPAsyncProtocol


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


def main():
    """Main entry point for the server."""
    parser = argparse.ArgumentParser(
        description="Lab Hop Protocol (LHP) Server with replay protection and TLS support"
    )
    parser.add_argument(
        "--tls",
        action="store_true",
        help="Enable TLS encryption (requires --certfile and --keyfile)"
    )
    parser.add_argument(
        "--certfile",
        type=str,
        help="Path to SSL certificate file (required with --tls)"
    )
    parser.add_argument(
        "--keyfile",
        type=str,
        help="Path to SSL private key file (required with --tls)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="Port to listen on (default: 8888)"
    )
    
    args = parser.parse_args()
    
    if args.tls and (not args.certfile or not args.keyfile):
        parser.error("--certfile and --keyfile are required when --tls is used")
    
    try:
        asyncio.run(_server_main(
            use_tls=args.tls,
            certfile=args.certfile,
            keyfile=args.keyfile,
            host=args.host,
            port=args.port
        ))
    except KeyboardInterrupt:
        print("\n✓ Server stopped")


if __name__ == "__main__":
    main()
