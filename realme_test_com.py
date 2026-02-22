import serial
import serial.tools.list_ports
import time
import os
import hmac
import hashlib

def crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
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
    print("Realme Buds T310 - SPP COM Port POC")
    
    ports = list(serial.tools.list_ports.comports())
    bt_ports = [p for p in ports if 'Bluetooth' in p.description or 'BTHENUM' in p.hwid]
    
    if not bt_ports:
        print("No Bluetooth COM ports found!")
        print("Please go to Windows Settings -> Bluetooth -> More Bluetooth Options -> COM Ports tab -> Add -> Outgoing -> Select Realme Buds T310")
        return
        
    print("Found potential Bluetooth COM ports:")
    for p in bt_ports:
        print(f"- {p.device}: {p.description}")
        
    com_port = input("\nEnter the COM port to use (e.g. COM3): ").strip().upper()
    if not com_port.startswith("COM"):
        return
        
    try:
        sock = serial.Serial(com_port, 9600, timeout=1)
        print(f"Opened {com_port} successfully!")
    except Exception as e:
        print(f"Failed to open {com_port}: {e}")
        return

    print("\nStarting Authentication Handshake...")
    app_random = os.urandom(16)
    auth_req = wrap_rmv_packet(1, 0, app_random)
    print(f"-> Sending Auth Request: {auth_req.hex()}")
    sock.write(auth_req)
    
    time.sleep(0.5)
    resp = sock.read(1024)
    print(f"<- Received: {resp.hex()}")
    
    if len(resp) < 58:
        print("Response too short or no response. Handshake failed.")
        return
        
    payload = resp[7:-2]
    device_hmac = payload[1:33]
    device_random = payload[33:49]
    
    expected_hmac = hmac.new(b"hmac_key", app_random, hashlib.sha256).digest()
    if device_hmac != expected_hmac:
        print("HMAC verification failed. Key might be different.")
    else:
        print("Device Identity Verified!")
        
    our_hmac = hmac.new(b"hmac_key", device_random, hashlib.sha256).digest()
    
    auth_resp_payload = bytearray([0x0A])
    auth_resp_payload.extend(our_hmac)
    
    auth_reply = wrap_rmv_packet(2, 1, bytes(auth_resp_payload))
    print(f"-> Sending Auth Reply: {auth_reply.hex()}")
    sock.write(auth_reply)
    
    time.sleep(0.5)
    resp2 = sock.read(1024)
    print(f"<- Received Auth Status: {resp2.hex()}")
    
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
            cmd_payload = bytes([0x02, 0x05, val])
            anc_packet = wrap_rmv_packet(4, seq, cmd_payload)
            print(f"-> Sending ANC Command: {anc_packet.hex()}")
            sock.write(anc_packet)
            seq += 1
            
            time.sleep(0.5)
            resp3 = sock.read(1024)
            print(f"<- Command Response: {resp3.hex()}")
        except ValueError:
            pass
            
    sock.close()

if __name__ == "__main__":
    main()
