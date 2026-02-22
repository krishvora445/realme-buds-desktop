import asyncio
import os
import hmac
import hashlib
from bleak import BleakClient

REALME_SERVICE_UUID = "000008a4-0000-1000-8000-00805f9b34fb"
REALME_WRITE_CHAR = "00000001-0000-1000-8000-00805f9b34fb"
REALME_NOTIFY_CHAR = "00000002-0000-1000-8000-00805f9b34fb"

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

def wrap_oppo_ble(payload: bytes) -> bytes:
    # OPPOv1Wrapper format: 0xAA (SOF), Length (Variable length encoded), Data
    # For small payloads, length is just 1 byte
    length = len(payload)
    # The 'l' method in OPPOv1Wrapper uses a 2-bit flag for Multi-package.
    # We assume Single package: flags = 0
    # Length byte (if < 128) is just the length.
    # Format: 0xAA | Length | (Data flags = 0x00) | Payload
    
    # Try the simplest form first based on the decompile:
    # bArr[0] = -86 (0xAA)
    # bArr[1] = Length
    # bArr[2] = Flags (0x00 for single package)
    
    frame = bytearray([0xAA, length, 0x00])
    frame.extend(payload)
    return bytes(frame)

async def main():
    print("Realme Buds T310 - OPPO BLE Protocol Test")
    mac = input("Enter Earbuds BLE MAC (e.g., 88:0E:85:46:18:9C): ").strip()
    
    if not mac:
        return
        
    print(f"\nConnecting to {mac} via BLE...")
    
    response_queue = asyncio.Queue()

    def notification_handler(sender, data):
        print(f"<- Received Notification: {data.hex()}")
        response_queue.put_nowait(data)

    try:
        async with BleakClient(mac) as client:
            print(f"✅ Connected to {mac}!")
            
            await client.start_notify(REALME_NOTIFY_CHAR, notification_handler)
            print("✅ Subscribed to notifications from EARBUDS.")
            
            print("\nStarting HMAC-SHA256 Authentication Handshake (OPPO WRAPPED)...")
            app_random = os.urandom(16)
            
            # Create the standard RMV packet
            rmv_auth_req = wrap_rmv_packet(1, 0, app_random)
            
            # Wrap it in the OPPO BLE frame
            oppo_auth_req = wrap_oppo_ble(rmv_auth_req)
            
            print(f"-> Sending Auth Request: {oppo_auth_req.hex()}")
            
            await client.write_gatt_char(REALME_WRITE_CHAR, oppo_auth_req, response=False)
            
            # Wait for Response
            try:
                resp = await asyncio.wait_for(response_queue.get(), timeout=3.0)
                print(f"Received Response! Format analyzer can take over from here to parse the handshake.")
            except asyncio.TimeoutError:
                print("❌ Timed out waiting for earbuds response. The OPPO wrapping might be different.")

    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
