import asyncio
import os
import hmac
import hashlib
from bleak import BleakClient

# Airoha BLE MMI Services
AIROHA_SERVICE_UUID = "5052494D-2DAB-0341-6972-6F6861424C45"
AIROHA_READ_CHAR = "43484152-2DAB-3141-6972-6F6861424C45"
AIROHA_WRITE_CHAR = "43484152-2DAB-3241-6972-6F6861424C45"

# HMAC Key from Realme Link
HMAC_KEY = b"hmac_key"

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

async def main():
    print("Realme Buds T310 - Airoha BLE POC")
    mac = input("Enter Earbuds MAC (e.g., 88:0E:85:46:18:C9): ").strip()
    
    if not mac:
        return
        
    print(f"Connecting to {mac} via BLE...")
    
    # Events for async synchronization
    auth_event = asyncio.Event()
    response_queue = asyncio.Queue()
    
    # Store dynamic variables inside the scope
    state = {
        "authenticated": False,
        "app_random": None
    }

    def notification_handler(sender, data):
        print(f"<- Received: {data.hex()}")
        response_queue.put_nowait(data)

    async with BleakClient(mac) as client:
        print(f"Connected to {mac}!")
        
        services = client.services
        airoha_service = None
        for s in services:
            if s.uuid.upper() == AIROHA_SERVICE_UUID.upper():
                airoha_service = s
                break
                
        if not airoha_service:
            print("❌ Earbuds connected, but Airoha MMI Service not found.")
            print("Make sure you entered the BLE MAC address if it differs from the Classic Bluetooth one.")
            return
            
        print("✅ Airoha MMI Service Verified!")
        await client.start_notify(AIROHA_READ_CHAR, notification_handler)
        
        # 1. Send our Random
        print("\nStarting Authentication...")
        state["app_random"] = os.urandom(16)
        auth_req = wrap_rmv_packet(1, 0, state["app_random"])
        print(f"-> Sending Auth Packet: {auth_req.hex()}")
        await client.write_gatt_char(AIROHA_WRITE_CHAR, auth_req, response=True)
        
        # 2. Wait for Response
        try:
            resp = await asyncio.wait_for(response_queue.get(), timeout=3.0)
            
            if len(resp) >= 58 and resp.startswith(b'\x52\x4D\x56'):
                payload = resp[7:-2]
                device_hmac = payload[1:33]
                device_random = payload[33:49]
                
                expected_hmac = hmac.new(b"hmac_key", state["app_random"], hashlib.sha256).digest()
                if device_hmac != expected_hmac:
                    print("❌ HMAC doesn't match. Keys might differ.")
                else:
                    print('✅ Device Identity Verified')
                    
                    # 3. Complete Handshake
                    our_hmac = hmac.new(b"hmac_key", device_random, hashlib.sha256).digest()
                    auth_resp_payload = bytearray([0x0A])
                    auth_resp_payload.extend(our_hmac)
                    
                    auth_reply = wrap_rmv_packet(2, 1, bytes(auth_resp_payload))
                    print(f"-> Sending Final HMAC: {auth_reply.hex()}")
                    await client.write_gatt_char(AIROHA_WRITE_CHAR, auth_reply, response=True)
                    
                    # Expect auth success response
                    resp2 = await asyncio.wait_for(response_queue.get(), timeout=2.0)
                    print("🎉 Authentication Complete!")
                    state["authenticated"] = True
            else:
                print("❌ Invalid response received")
        except asyncio.TimeoutError:
            print("❌ Timed out waiting for earbuds response")
            return
            
        if not state["authenticated"]:
            return
            
        print("\n--- ANC CONTROL OVER BLE ---")
        print("1: Noise Canceling")
        print("2: Normal")
        print("3: Transparent")
        
        seq = 2
        while True:
            mode = input("Select ANC mode (1-3, q to quit): ").strip()
            if mode.lower() == 'q':
                break
                
            try:
                val = int(mode)
                if val in [1, 2, 3]:
                    payload = bytes([0x02, 0x05, val])
                    anc_cmd = wrap_rmv_packet(4, seq, payload)
                    print(f"-> Sending ANC Cmd: {anc_cmd.hex()}")
                    await client.write_gatt_char(AIROHA_WRITE_CHAR, anc_cmd, response=True)
                    seq += 1
            except ValueError:
                pass

if __name__ == "__main__":
    asyncio.run(main())
