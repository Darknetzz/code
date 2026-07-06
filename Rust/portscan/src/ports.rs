pub const DEFAULT_PORTS: &[u16] = &[
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 3306, 3389, 5432, 5900, 8080, 8443,
];

pub const PORT_SERVICES: &[(u16, &str)] = &[
    (21, "FTP"),
    (22, "SSH"),
    (23, "Telnet"),
    (25, "SMTP"),
    (53, "DNS"),
    (80, "HTTP"),
    (110, "POP3"),
    (135, "MS RPC"),
    (139, "NetBIOS"),
    (143, "IMAP"),
    (443, "HTTPS"),
    (445, "SMB"),
    (3306, "MySQL"),
    (3389, "RDP"),
    (5432, "PostgreSQL"),
    (5900, "VNC"),
    (8080, "HTTP-Proxy"),
    (8443, "HTTPS-Alt"),
];

pub fn parse_ports(spec: &str) -> Vec<u16> {
    let mut ports = std::collections::BTreeSet::new();

    for part in spec.split(',') {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }
        if let Some((start_s, end_s)) = part.split_once('-') {
            match (start_s.trim().parse::<u16>(), end_s.trim().parse::<u16>()) {
                (Ok(mut start), Ok(mut end)) => {
                    if start > end {
                        std::mem::swap(&mut start, &mut end);
                    }
                    for p in start..=end {
                        ports.insert(p);
                    }
                }
                _ => eprintln!("[!] Invalid port range: {part}"),
            }
        } else {
            match part.parse::<u16>() {
                Ok(port) if (1..=65535).contains(&port) => {
                    ports.insert(port);
                }
                Ok(port) => eprintln!("[!] Port out of range (1-65535): {port}"),
                Err(_) => eprintln!("[!] Invalid port: {part}"),
            }
        }
    }

    ports.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_single_and_ranges() {
        assert_eq!(parse_ports("80"), vec![80]);
        assert_eq!(parse_ports("80,443"), vec![80, 443]);
        assert_eq!(parse_ports("1-3"), vec![1, 2, 3]);
        assert_eq!(parse_ports("3-1"), vec![1, 2, 3]);
    }
}
