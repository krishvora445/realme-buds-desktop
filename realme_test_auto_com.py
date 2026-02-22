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

def try_handshake(com_port):
    try:
        # Realme buds usually communicate over SPP at 9600 or 115200 baud
        sock = serial.Serial(com_port, 9600, timeout=1.5, write_timeout=1.5)
    except Exception as e:
        return False, f"Failed to open: {e}"

    try:
        app_random = os.urandom(16)
        auth_req = wrap_rmv_packet(1, 0, app_random)
        sock.write(auth_req)
        
        resp = sock.read(1024)
        
        if len(resp) >= 58 and resp.startswith(b'\x52\x4D\x56'):
            payload = resp[7:-2]
            device_hmac = payload[1:33]
            device_random = payload[33:49]
            
            expected_hmac = hmac.new(b"hmac_key", app_random, hashlib.sha256).digest()
            if device_hmac == expected_hmac:
                our_hmac = hmac.new(b"hmac_key", device_random, hashlib.sha256).digest()
                auth_resp_payload = bytearray([0x0A])
                auth_resp_payload.extend(our_hmac)
                auth_reply = wrap_rmv_packet(2, 1, bytes(auth_resp_payload))
                sock.write(auth_reply)
                
                resp2 = sock.read(1024)
                return True, sock
        
        sock.close()
        return False, "No valid response"
    except Exception as e:
        sock.close()
        return False, f"Error during handshake: {e}"

def main():
    print("Realme Buds T310 - Auto COM Port Scanner")
    print("Scanning available Bluetooth COM ports...")
    
    ports = list(serial.tools.list_ports.comports())
    bt_ports = [p.device for p in ports if 'Bluetooth' in p.description or 'BTHENUM' in p.hwid]
    
    if not bt_ports:
        print("No Bluetooth COM ports found in the system.")
        return
        
    print(f"Found {len(bt_ports)} potential ports: {', '.join(bt_ports)}")
    
    active_sock = None
    active_port = None
    
    for port in bt_ports:
        print(f"\nTrying {port}...")
        success, result = try_handshake(port)
        if success:
            print(f"✅ SUCCESS! Authenticated with Realme Buds on {port}")
            active_sock = result
            active_port = port
            break
        else:
            print(f"❌ Failed: {result}")
            
    if not active_sock:
        print("\nCould not authenticate on any COM port.")
        print("Make sure the earbuds are deeply connected (try playing audio first).")
        return
        
    print("\n--- ANC CONTROL READY ---")
    print("1: Noise Canceling")
    print("2: Normal")
    print("3: Transparent")
    
    seq = 2
    while True:
        try:
            mode = input(f"\n[{active_port}] Select ANC mode (1-3, or q to quit): ").strip()
            if mode.lower() == 'q':
                break
            
            val = int(mode)
            if val not in [1, 2, 3]:
                continue
                
            cmd_payload = bytes([0x02, 0x05, val])
            anc_packet = wrap_rmv_packet(4, seq, cmd_payload)
            print(f"-> Sending ANC Command: {anc_packet.hex()}")
            active_sock.write(anc_packet)
            seq += 1
            
            time.sleep(0.3)
            resp3 = active_sock.read(1024)
            print(f"<- Command Response: {resp3.hex() if resp3 else 'No response'}")
        except ValueError:
            pass
        except Exception as e:
            print(f"Connection lost: {e}")
            break
            
    active_sock.close()

if __name__ == "__main__":
    main()
