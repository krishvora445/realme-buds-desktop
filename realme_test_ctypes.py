import ctypes
import ctypes.wintypes as wintypes
import os
import hmac
import hashlib
import time

ws2_32 = ctypes.windll.ws2_32

# Winsock Constants
AF_BTH = 32
SOCK_STREAM = 1
BTHPROTO_RFCOMM = 3
INVALID_SOCKET = -1
SOCKET_ERROR = -1

class WSADATA(ctypes.Structure):
    _fields_ = [
        ("wVersion", ctypes.c_uint16),
        ("wHighVersion", ctypes.c_uint16),
        ("szDescription", ctypes.c_char * 257),
        ("szSystemStatus", ctypes.c_char * 129),
        ("iMaxSockets", ctypes.c_ushort),
        ("iMaxUdpDg", ctypes.c_ushort),
        ("lpVendorInfo", ctypes.c_char_p),
    ]

class SOCKADDR_BTH(ctypes.Structure):
    _fields_ = [
        ("addressFamily", ctypes.c_ushort),
        ("btAddr", ctypes.c_ulonglong),
        ("serviceClassId", ctypes.c_ubyte * 16),
        ("port", ctypes.c_ulong),
    ]

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
    
def mac_to_int(mac_str):
    return int(mac_str.replace(":", ""), 16)

class BthSocket:
    def __init__(self):
        wsaData = WSADATA()
        ws2_32.WSAStartup(0x0202, ctypes.byref(wsaData))
        self.sock = ws2_32.socket(AF_BTH, SOCK_STREAM, BTHPROTO_RFCOMM)
        if self.sock == INVALID_SOCKET:
            raise Exception("Failed to create socket")
            
    def connect(self, mac_str, port=1):
        addr = SOCKADDR_BTH()
        addr.addressFamily = AF_BTH
        addr.btAddr = mac_to_int(mac_str)
        addr.port = port
        
        ret = ws2_32.connect(self.sock, ctypes.byref(addr), ctypes.sizeof(addr))
        if ret == SOCKET_ERROR:
            err = ws2_32.WSAGetLastError()
            raise Exception(f"Connect failed with error code: {err}")
            
    def send(self, data):
        buf = ctypes.create_string_buffer(data)
        ret = ws2_32.send(self.sock, buf, len(data), 0)
        if ret == SOCKET_ERROR:
            raise Exception("Send failed")
            
    def recv(self, size=1024):
        buf = ctypes.create_string_buffer(size)
        ret = ws2_32.recv(self.sock, buf, size, 0)
        if ret == SOCKET_ERROR:
            return b""
        elif ret == 0:
            return b""
        return buf.raw[:ret]
        
    def close(self):
        ws2_32.closesocket(self.sock)
        ws2_32.WSACleanup()

def main():
    print("Realme Buds T310 - RFCOMM POC (ctypes version)")
    mac = input("Enter MAC (e.g., 88:0E:85:46:18:C9): ").strip()
    if not mac:
        return
        
    sock = BthSocket()
    
    # Try connecting to port 1, 2, 3...
    connected = False
    for port in range(1, 6):
        try:
            print(f"Trying to connect to {mac} on RFCOMM channel {port}...")
            sock.connect(mac, port)
            connected = True
            print(f"Connected on channel {port}!")
            break
        except Exception as e:
            print(f"Channel {port} failed: {e}")
            
    if not connected:
        print("Could not connect to the device. Please make sure they are connected and paired in Windows settings.")
        return

    # Step 1: Send 16 random bytes (Command 01)
    print("Starting Authentication Handshake...")
    app_random = os.urandom(16)
    auth_req = wrap_rmv_packet(1, 0, app_random)
    print(f"-> Sending Auth Request: {auth_req.hex()}")
    sock.send(auth_req)
    
    # Step 2: Receive 49 bytes response
    time.sleep(0.5)
    resp = sock.recv(1024)
    print(f"<- Received: {resp.hex()}")
    
    if len(resp) < 58: # RMV header (7) + Payload (49) + CRC (2)
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
    sock.send(auth_reply)
    
    time.sleep(0.5)
    resp2 = sock.recv(1024)
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
            sock.send(anc_packet)
            seq += 1
            
            time.sleep(0.5)
            resp3 = sock.recv(1024)
            print(f"<- Command Response: {resp3.hex()}")
        except ValueError:
            pass
            
    sock.close()

if __name__ == "__main__":
    main()
