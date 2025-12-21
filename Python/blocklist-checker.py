import socket
import urllib.request
import json

def get_public_ip():
    """Get the public IP address by querying external services."""
    services = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/all.json",
        "https://api.ip.sb/ip",
        "https://icanhazip.com"
    ]
    
    for service in services:
        try:
            if service.endswith('.json'):
                with urllib.request.urlopen(service, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    if 'ip' in data:
                        return data['ip']
                    elif 'ip_addr' in data:
                        return data['ip_addr']
            else:
                with urllib.request.urlopen(service, timeout=5) as response:
                    ip = response.read().decode().strip()
                    if ip and len(ip.split('.')) == 4:
                        return ip
        except Exception:
            continue
    
    raise Exception("Could not determine public IP address")

def check_rbl(ip):
    # Common RBLs for 2025
    rbls = [
        "zen.spamhaus.org",
        "bl.spamcop.net",
        "b.barracudacentral.org",
        "dnsbl.sorbs.net",
        "bl.blocklist.de"
    ]
    
    # Reverse the IP: 1.2.3.4 -> 4.3.2.1
    reversed_ip = ".".join(ip.split(".")[::-1])
    
    print(f"--- Checking Reputation for {ip} ---")
    for rbl in rbls:
        query = f"{reversed_ip}.{rbl}"
        try:
            socket.gethostbyname(query)
            print(f"[!] LISTED: {rbl}")
        except socket.gaierror:
            print(f"[✓] Clean: {rbl}")

if __name__ == "__main__":
    try:
        target_ip = get_public_ip()
        print(f"Detected public IP: {target_ip}\n")
    except Exception as e:
        print(f"Error getting IP address: {e}")
        exit(1)
    
    check_rbl(target_ip)