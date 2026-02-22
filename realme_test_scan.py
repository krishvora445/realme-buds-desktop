import asyncio
from bleak import BleakScanner

async def run():
    print("Scanning for Bluetooth Low Energy devices for 5 seconds...")
    devices = await BleakScanner.discover(timeout=5.0)
    print("\n--- Discovered BLE Devices ---")
    for d in devices:
        print(f"[{d.address}] {d.name or 'Unknown Device'}")
        if d.details and 'props' in d.details:
            print(f"  Props: {d.details['props']}")

if __name__ == "__main__":
    asyncio.run(run())
