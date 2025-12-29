#!/usr/bin/env python3
"""
PyPortScanner - A simple and efficient port scanner
Scans one or multiple IP addresses for open ports
"""

import socket
import concurrent.futures
from typing import List, Tuple, Optional
from datetime import datetime
import typer

# Default common ports to scan
DEFAULT_PORTS = [
    21,    # FTP
    22,    # SSH
    23,    # Telnet
    25,    # SMTP
    53,    # DNS
    80,    # HTTP
    110,   # POP3
    135,   # MS RPC
    139,   # NetBIOS
    143,   # IMAP
    443,   # HTTPS
    445,   # SMB
    3306,  # MySQL
    3389,  # RDP
    5432,  # PostgreSQL
    5900,  # VNC
    8080,  # HTTP Proxy
    8443,  # HTTPS Alt
]

# Common port to service name mapping
PORT_SERVICES = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    135: "MS RPC",
    139: "NetBIOS",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    8080: "HTTP-Proxy",
    8443: "HTTPS-Alt",
}


def scan_port(ip: str, port: int, timeout: float = 1.0) -> Tuple[int, bool]:
    """
    Scan a single port on the given IP address.
    
    Args:
        ip: IP address to scan
        port: Port number to scan
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple of (port, is_open)
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return (port, result == 0)
    except socket.gaierror:
        return (port, False)
    except socket.error:
        return (port, False)


def scan_host(ip: str, ports: List[int], timeout: float = 1.0, max_workers: int = 100) -> List[int]:
    """
    Scan multiple ports on a single host.
    
    Args:
        ip: IP address to scan
        ports: List of ports to scan
        timeout: Connection timeout in seconds
        max_workers: Maximum number of concurrent threads
        
    Returns:
        List of open ports
    """
    open_ports = []
    scanned_count = 0
    total_ports = len(ports)
    last_percentage = 0
    
    print(f"\n[*] Scanning {ip}...")
    print(f"[*] Ports to scan: {total_ports}")
    print(f"[*] Progress: 0/{total_ports} (0.0%)")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_port = {executor.submit(scan_port, ip, port, timeout): port for port in ports}
        
        for future in concurrent.futures.as_completed(future_to_port):
            port, is_open = future.result()
            scanned_count += 1
            
            if is_open:
                open_ports.append(port)
                service = PORT_SERVICES.get(port, "Unknown")
                print(f"[+] Port {port:5d} - OPEN ({service})")
            
            # Show progress every 1% or every 100 ports, whichever is more frequent
            current_percentage = int((scanned_count / total_ports) * 100)
            if (current_percentage > last_percentage) or (scanned_count % 100 == 0) or (scanned_count == total_ports):
                percentage = (scanned_count / total_ports) * 100
                print(f"[*] Progress: {scanned_count}/{total_ports} ({percentage:.1f}%)", flush=True)
                last_percentage = current_percentage
    
    return sorted(open_ports)


def parse_ports(port_string: str) -> List[int]:
    """
    Parse port specification string into list of ports.
    Supports formats: "80", "80,443,8080", "1-100", "1-100,443,8080-8090"
    
    Args:
        port_string: Port specification string
        
    Returns:
        List of port numbers
    """
    ports = set()
    
    for part in port_string.split(','):
        part = part.strip()
        if '-' in part:
            # Range of ports
            try:
                start, end = map(int, part.split('-'))
                if start > end:
                    start, end = end, start
                ports.update(range(start, end + 1))
            except ValueError:
                print(f"[!] Invalid port range: {part}")
        else:
            # Single port
            try:
                port = int(part)
                if 1 <= port <= 65535:
                    ports.add(port)
                else:
                    print(f"[!] Port out of range (1-65535): {port}")
            except ValueError:
                print(f"[!] Invalid port: {part}")
    
    return sorted(list(ports))


def validate_ip(ip: str) -> bool:
    """
    Validate IP address format.
    
    Args:
        ip: IP address string
        
    Returns:
        True if valid, False otherwise
    """
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


app = typer.Typer(
    help="PyPortScanner - Scan ports on one or multiple IP addresses",
    add_completion=False
)


@app.command()
def main(
    ips: List[str] = typer.Argument(
        ...,
        help="One or more IP addresses to scan"
    ),
    ports: Optional[str] = typer.Option(
        None,
        "-p", "--ports",
        help='Ports to scan (default: common ports). Format: "80" or "80,443" or "1-1000" or "1-100,443,8080-8090"'
    ),
    timeout: float = typer.Option(
        1.0,
        "-t", "--timeout",
        help="Connection timeout in seconds"
    ),
    workers: int = typer.Option(
        100,
        "-w", "--workers",
        help="Maximum number of concurrent threads"
    )
):
    """
    PyPortScanner - Scan ports on one or multiple IP addresses
    
    Examples:
    
        pyportscanner.py 192.168.1.1
        
        pyportscanner.py 192.168.1.1 192.168.1.2
        
        pyportscanner.py 192.168.1.1 -p 80
        
        pyportscanner.py 192.168.1.1 -p 80,443,8080
        
        pyportscanner.py 192.168.1.1 -p 1-1000
        
        pyportscanner.py 192.168.1.1 -p 1-100,443,8080-8090
        
        pyportscanner.py 192.168.1.1 -t 2 -w 200
    """
    # Validate IPs
    valid_ips = []
    for ip in ips:
        if validate_ip(ip):
            valid_ips.append(ip)
        else:
            typer.echo(f"[!] Invalid IP address: {ip}")
    
    if not valid_ips:
        typer.echo("[!] No valid IP addresses provided")
        raise typer.Exit(1)
    
    # Parse ports
    if ports:
        port_list = parse_ports(ports)
        if not port_list:
            typer.echo("[!] No valid ports specified")
            raise typer.Exit(1)
    else:
        port_list = DEFAULT_PORTS
        typer.echo(f"[*] Using default port list ({len(port_list)} ports)")
    
    # Print scan info
    typer.echo("=" * 60)
    typer.echo(f"PyPortScanner - Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    typer.echo("=" * 60)
    typer.echo(f"[*] Targets: {', '.join(valid_ips)}")
    typer.echo(f"[*] Timeout: {timeout}s")
    typer.echo(f"[*] Worker threads: {workers}")
    
    # Scan each host
    start_time = datetime.now()
    results = {}
    
    for ip in valid_ips:
        try:
            open_ports = scan_host(ip, port_list, timeout, workers)
            results[ip] = open_ports
            
            if open_ports:
                typer.echo(f"\n[*] Summary for {ip}: {len(open_ports)} open port(s)")
            else:
                typer.echo(f"\n[*] Summary for {ip}: No open ports found")
                
        except KeyboardInterrupt:
            typer.echo("\n\n[!] Scan interrupted by user")
            break
        except Exception as e:
            typer.echo(f"\n[!] Error scanning {ip}: {e}")
    
    # Print final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    typer.echo("\n" + "=" * 60)
    typer.echo("Scan Complete")
    typer.echo("=" * 60)
    
    for ip, open_ports in results.items():
        if open_ports:
            typer.echo(f"\n{ip}:")
            for port in open_ports:
                service = PORT_SERVICES.get(port, "Unknown")
                typer.echo(f"  {port:5d}/tcp - {service}")
        else:
            typer.echo(f"\n{ip}: No open ports")
    
    typer.echo(f"\n[*] Scan completed in {duration:.2f} seconds")


if __name__ == "__main__":
    app()
