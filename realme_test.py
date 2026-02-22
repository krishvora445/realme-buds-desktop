import socket
import hmac
import hashlib
import os
import struct

def crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        # (((i << 8) | (i >>> 8)) & 0xFFFF) ^ (bArr[i2] & 255)
        crc = ((crc << 8) | (crc >> 8)) & 0xFFFF
        crc ^= byte
        crc ^= (crc & 0xFF) >> 4
        crc ^= (crc << 12) & 0xFFFF
        crc ^= (crc & 0xFF) << 5
        crc &= 0xFFFF
    return crc

def wrap_rmv_packet(cmd: int, seq: int, payload: bytes) -> bytes:
    length = len(payload)
    packet = bytearray([0x52, 0x4D, 0x56, cmd, seq, (length >> 8) & 0xFF, length & 0xFF])
    packet.extend(payload)
    c = crc16(packet)
    packet.extend([(c >> 8) & 0xFF, c & 0xFF])
    return bytes(packet)

def main():
    print("Realme Buds T310 - RFCOMM POC")
    print("Please run this script and input your Earbuds MAC Address.")
    mac = input("Enter MAC (e.g., AA:BB:CC:DD:EE:FF): ").strip()
    if not mac:
        print("Invalid MAC.")
        return
        
    port = 1
    print(f"Connecting to {mac} on channel {port} (SPP)...")
    
    sock = socket.socket(socket.AF_BTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    try:
        sock.connect((mac, port))
        print("Connected!")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # Step 1: Send 16 random bytes (Command 01)
    print("Starting Authentication Handshake...")
    app_random = os.urandom(16)
    auth_req = wrap_rmv_packet(1, 0, app_random)
    print(f"-> Sending Auth Request: {auth_req.hex()}")
    sock.send(auth_req)
    
    # Step 2: Receive 49 bytes response
    resp = sock.recv(1024)
    print(f"<- Received: {resp.hex()}")
    
    if len(resp) < 58: # RMV header (7) + Payload (49) + CRC (2)
        print("Response too short")
        return
        
    payload = resp[7:-2]
    # payload[0] = something (maybe 10)
    # payload[1:33] = device's hmac of our random bytes
    # payload[33:49] = device's random bytes
    
    device_hmac = payload[1:33]
    device_random = payload[33:49]
    
    # Verify device
    expected_hmac = hmac.new(b"hmac_key", app_random, hashlib.sha256).digest()
    if device_hmac != expected_hmac:
        print("HMAC verification failed. Key might be different.")
    else:
        print("Device Identity Verified!")
        
    # Step 3: Send our HMAC of the device's random bytes (Command 02)
    our_hmac = hmac.new(b"hmac_key", device_random, hashlib.sha256).digest()
    
    # Payload is 0x0A (10) followed by the 32-byte HMAC
    auth_resp_payload = bytearray([0x0A])
    auth_resp_payload.extend(our_hmac)
    
    auth_reply = wrap_rmv_packet(2, 1, bytes(auth_resp_payload))
    print(f"-> Sending Auth Reply: {auth_reply.hex()}")
    sock.send(auth_reply)
    
    # Wait for success
    resp2 = sock.recv(1024)
    print(f"<- Received Auth Status: {resp2.hex()}")
    # Should be cmd=02, payload=[0x0A]
    
    print("\nAuth complete! You can now send ANC commands.")
    print("1: Noise Canceling")
    print("2: Normal")
    print("3: Transparent")
    
    seq = 2
    while True:
        mode = input("Select ANC mode (1-3, or q to quit): ").strip()
        if mode.lower() == 'q':
            break
        try:
            val = int(mode)
            if val not in [1, 2, 3]:
                continue
                
            # Command 04, Payload: 02 (set) 05 (ANC key) val (1-3)
            # Actually VoiceReductionType:
            # 1: Noise Canceling (VoiceReduction)
            # 2: Normal (Default)
            # 3: Transparent
            cmd_payload = bytes([0x02, 0x05, val])
            anc_packet = wrap_rmv_packet(4, seq, cmd_payload)
            print(f"-> Sending ANC Command: {anc_packet.hex()}")
            sock.send(anc_packet)
            seq += 1
            
            # Wait for response
            resp3 = sock.recv(1024)
            print(f"<- Command Response: {resp3.hex()}")
        except ValueError:
            pass
            
    sock.close()

if __name__ == "__main__":
    main()
