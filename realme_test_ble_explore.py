import asyncio
from bleak import BleakClient

async def main():
    print("Realme Buds T310 - BLE Service Explorer")
    mac = input("Enter Earbuds BLE MAC (e.g., 88:0E:85:46:18:9C): ").strip()
    
    if not mac:
        return
        
    print(f"\nConnecting to {mac}...")
    try:
        async with BleakClient(mac) as client:
            print(f"✅ Connected to {mac}!\n")
            print("--- Discovering GATT Services ---")
            
            services = client.services
            if not services:
                print("No services found.")
                return
                
            for service in services:
                print(f"[Service] {service.uuid} - {service.description}")
                for char in service.characteristics:
                    props = ",".join(char.properties)
                    print(f"  └─ [Characteristic] {char.uuid} ({props})")
                    for descriptor in char.descriptors:
                        print(f"       └─ [Descriptor] {descriptor.uuid}")
            
            print("\nDiscovery Complete.")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
