"""
Lab Hop Protocol (LHP) - Protocol Implementation

State-based protocol implementation for asynchronous communication.
Includes replay protection and packet validation.
"""

import asyncio
import struct
import time


class LHPProtocol:
    """
    Lab Hop Protocol implementation.
    
    Protocol format:
    - STX (1 byte): Start byte (0x02)
    - Length (2 bytes): Payload length (big-endian)
    - CMD (1 byte): Command ID (0-255)
    - Timestamp (4 bytes): Unix timestamp for replay protection (big-endian)
    - Payload (variable): Command data
    - Checksum (1 byte): XOR checksum of payload
    
    Security features:
    - Replay protection using timestamps (4-byte uint32)
    - XOR checksum for data integrity
    """
    STX = 0x02
    HEADER_FORMAT = "!BHBI"  # STX (1B), Length (2B), CMD (1B), Timestamp (4B) - Big Endian
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    TIMESTAMP_WINDOW_SECONDS = 300  # 5 minutes - reject packets older than this
    
    @staticmethod
    def create_packet(cmd_id, data_bytes):
        """
        Create a packet with timestamp for replay protection.
        
        Args:
            cmd_id: Command ID (0-255)
            data_bytes: Payload data (bytes)
            
        Returns:
            Complete packet as bytes
        """
        length = len(data_bytes)
        timestamp = int(time.time())
        
        # Calculate XOR checksum over payload
        checksum = 0
        for b in data_bytes:
            checksum ^= b
        
        header = struct.pack(LHPProtocol.HEADER_FORMAT, 
                            LHPProtocol.STX, length, cmd_id, timestamp)
        return header + data_bytes + struct.pack("B", checksum)


class LHPAsyncProtocol(asyncio.Protocol):
    """
    State-based implementation of Lab Hop Protocol using asyncio.Protocol.
    This is how 'real' protocols (like HTTP/2 or SSH) are often implemented.
    
    Security features:
    - Replay protection using timestamps (4-byte uint32)
    - Duplicate nonce detection
    - XOR checksum validation
    """
    STX = LHPProtocol.STX
    HEADER_FORMAT = LHPProtocol.HEADER_FORMAT
    HEADER_SIZE = LHPProtocol.HEADER_SIZE
    TIMESTAMP_WINDOW_SECONDS = LHPProtocol.TIMESTAMP_WINDOW_SECONDS
    _seen_nonces = set()  # Class-level set to track seen nonces across connections
    
    @classmethod
    def _cleanup_old_nonces(cls):
        """Remove old timestamps that are outside the window."""
        current_time = int(time.time())
        cutoff = current_time - cls.TIMESTAMP_WINDOW_SECONDS
        cls._seen_nonces = {nonce for nonce in cls._seen_nonces if nonce > cutoff}

    def __init__(self):
        self.buffer = bytearray()
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        print(f"Connection established from {transport.get_extra_info('peername')}")

    def data_received(self, data):
        """Called automatically whenever bytes hit the network stack."""
        self.buffer.extend(data)
        self._process_buffer()

    def _process_buffer(self):
        """Process incoming buffer, extracting complete packets."""
        while len(self.buffer) >= self.HEADER_SIZE:
            # 1. Look for the START_BYTE
            if self.buffer[0] != self.STX:
                self.buffer.pop(0)  # Discard junk until we find STX
                continue

            # 2. Peek at the length (bytes 1 and 2)
            payload_len = struct.unpack_from("!H", self.buffer, 1)[0]
            total_expected_size = self.HEADER_SIZE + payload_len + 1  # +1 for Checksum

            # 3. Check if the full packet has arrived
            if len(self.buffer) < total_expected_size:
                break  # Wait for more data

            # 4. Extract the full packet
            packet = self.buffer[:total_expected_size]
            del self.buffer[:total_expected_size]

            self._handle_packet(packet)

    def _handle_packet(self, packet):
        """Handle a complete packet."""
        # Unpack header
        _, length, cmd_id, timestamp = struct.unpack_from(self.HEADER_FORMAT, packet)
        payload = packet[self.HEADER_SIZE : self.HEADER_SIZE + length]
        received_checksum = packet[-1]

        # Replay Protection: Check timestamp validity
        current_time = int(time.time())
        if timestamp < (current_time - self.TIMESTAMP_WINDOW_SECONDS):
            print("Dropped packet: timestamp too old (replay attack?)")
            return
        if timestamp > (current_time + 60):  # Allow 1 minute clock skew
            print("Dropped packet: timestamp too far in future")
            return
        
        # Check if we've seen this nonce before (replay detection)
        self._cleanup_old_nonces()
        if timestamp in self._seen_nonces:
            print("Dropped packet: duplicate nonce detected (replay attack)")
            return
        self._seen_nonces.add(timestamp)

        # Checksum Validation
        calculated_checksum = 0
        for b in payload:
            calculated_checksum ^= b

        if received_checksum == calculated_checksum:
            print(f"Received Command {cmd_id}: {payload.decode(errors='ignore')}")
            # Logic: If cmd_id == 0x01, trigger an Ansible playbook, etc.
        else:
            print("Dropped corrupted packet.")
