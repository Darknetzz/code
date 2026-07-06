pub const STX: u8 = 0x02;
pub const HEADER_SIZE: usize = 8; // STX(1) + len(2) + cmd(1) + ts(4)
pub const TIMESTAMP_WINDOW_SECONDS: u32 = 300;

#[derive(Debug, Clone)]
pub struct LhpPacket {
    pub cmd_id: u8,
    pub timestamp: u32,
    pub payload: Vec<u8>,
    pub checksum: u8,
}

pub fn create_packet(cmd_id: u8, data: &[u8]) -> Vec<u8> {
    let length = data.len() as u16;
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as u32)
        .unwrap_or(0);
    let checksum = data.iter().fold(0u8, |acc, b| acc ^ b);
    let mut packet = Vec::with_capacity(HEADER_SIZE + data.len() + 1);
    packet.push(STX);
    packet.extend_from_slice(&length.to_be_bytes());
    packet.push(cmd_id);
    packet.extend_from_slice(&timestamp.to_be_bytes());
    packet.extend_from_slice(data);
    packet.push(checksum);
    packet
}

pub fn parse_packet(bytes: &[u8]) -> Option<LhpPacket> {
    if bytes.len() < HEADER_SIZE + 1 {
        return None;
    }
    if bytes[0] != STX {
        return None;
    }
    let length = u16::from_be_bytes([bytes[1], bytes[2]]) as usize;
    let cmd_id = bytes[3];
    let timestamp = u32::from_be_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
    let payload_end = HEADER_SIZE + length;
    if bytes.len() < payload_end + 1 {
        return None;
    }
    let payload = bytes[HEADER_SIZE..payload_end].to_vec();
    let checksum = bytes[payload_end];
    Some(LhpPacket {
        cmd_id,
        timestamp,
        payload,
        checksum,
    })
}

pub fn cleanup_old_nonces(seen: &mut std::collections::HashSet<u32>, now: u32) {
    let cutoff = now.saturating_sub(TIMESTAMP_WINDOW_SECONDS);
    seen.retain(|nonce| *nonce > cutoff);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_packet() {
        let raw = create_packet(1, b"Hello");
        let pkt = parse_packet(&raw).expect("parse");
        assert_eq!(pkt.cmd_id, 1);
        assert_eq!(pkt.payload, b"Hello");
    }
}
