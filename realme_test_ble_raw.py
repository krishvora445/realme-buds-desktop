import asyncio
from bleak import BleakClient

# Realme Custom BLE Service
REALME_SERVICE_UUID = "000008a4-0000-1000-8000-00805f9b34fb"
REALME_WRITE_CHAR = "00000001-0000-1000-8000-00805f9b34fb"
REALME_NOTIFY_CHAR = "00000002-0000-1000-8000-00805f9b34fb"

# Try raw payloads without the 9-byte RMV header
def get_raw_anc_payload(mode: int) -> bytes:
    # 02 = SET, 05 = ANC Status, val = mode (1: ANC, 2: Normal, 3: Transparent)
    return bytes([0x02, 0x05, mode])

async def main():
    print("Realme Buds T310 - BLE Raw Command POC")
    mac = input("Enter Earbuds BLE MAC (e.g., 88:0E:85:46:18:9C): ").strip()
    
    if not mac:
        return
        
    print(f"\nConnecting to {mac} via BLE...")
    
    def notification_handler(sender, data):
        print(f"<- Received Notification: {data.hex()}")

    try:
        async with BleakClient(mac) as client:
            print(f"✅ Connected to {mac}!")
            
            await client.start_notify(REALME_NOTIFY_CHAR, notification_handler)
            print("✅ Subscribed to notifications from EARBUDS.")
            
            print("\n--- ANC RAW BLE CONTROL ---")
            print("1: Noise Canceling")
            print("2: Normal")
            print("3: Transparent")
            
            while True:
                mode = input("\nSelect ANC mode (1-3, q to quit): ").strip()
                if mode.lower() == 'q':
                    break
                    
                try:
                    val = int(mode)
                    if val in [1, 2, 3]:
                        # Try sending just the raw 3-byte command
                        raw_payload = get_raw_anc_payload(val)
                        print(f"-> Sending Raw Payload: {raw_payload.hex()}")
                        
                        # Characteristic 0001 is write-without-response
                        await client.write_gatt_char(REALME_WRITE_CHAR, raw_payload, response=False)
                        print("Packet sent!")
                except ValueError:
                    pass
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
