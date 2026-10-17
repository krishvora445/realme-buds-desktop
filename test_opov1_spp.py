import asyncio
import sys
import uuid
from winsdk.windows.devices.bluetooth import BluetoothDevice
from winsdk.windows.devices.bluetooth.rfcomm import RfcommServiceId
from winsdk.windows.networking.sockets import StreamSocket
from winsdk.windows.storage.streams import DataWriter, DataReader, InputStreamOptions

# Standard SPP UUID and Oppo/Realme custom UUID
SPP_UUID = uuid.UUID("00001101-0000-1000-8000-00805F9B34FB")
OPO_UUID = uuid.UUID("0000079A-D102-11E1-9B23-00025B00A5A5")

# OPOv1 Protocol Packets
# Handshake Step 1: HELLO
HELLO_PKT = bytes.fromhex("AA070000000123000012")
# Handshake Step 2: REGISTER (with ecosystem token B5 50 A0 69)
REGISTER_PKT = bytes.fromhex("AA0C0000008541050000B550A069")

# ANC Control Packets
ANC_ON = bytes.fromhex("AA0A00000404420300010101")           # Mode 0x01: Noise Cancellation
ANC_TRANSPARENCY = bytes.fromhex("AA0A00000404420300010102") # Mode 0x02: Transparency
ANC_OFF = bytes.fromhex("AA0A00000404400300010104")          # Mode 0x04: Normal / ANC Off

# Query ANC status
ANC_QUERY = bytes.fromhex("AA070000048220000000")
# Battery Query
BATTERY_QUERY = bytes.fromhex("AA060000068200")

async def read_loop(reader: DataReader):
    print("Listening for earbuds response...")
    while True:
        try:
            count = await reader.load_async(1024)
            if count > 0:
                resp = reader.read_bytes(count)
                hex_str = bytes(resp).hex().upper()
                formatted_hex = " ".join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
                print(f"\n<- RECEIVED RX: {formatted_hex}")
            else:
                print("\n<- Remote socket closed")
                break
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"\nRead loop error: {e}")
            break

async def main():
    mac_str = "88:0E:85:46:18:C9"
    if len(sys.argv) > 1:
        mac_str = sys.argv[1].strip()
        
    print(f"=== Realme Buds T310 - OPOv1 Protocol Test ===")
    print(f"Target MAC: {mac_str}")
    
    mac_int = int(mac_str.replace(":", ""), 16)
    device = await BluetoothDevice.from_bluetooth_address_async(mac_int)
    if not device:
        print("Device not found! Ensure Realme Buds T310 is paired and connected.")
        return

    print(f"Found Device: {device.name}")
    
    # Check RFCOMM services
    rfcomm_services = await device.get_rfcomm_services_async()
    print(f"Discovered {len(rfcomm_services.services)} RFCOMM services:")
    for s in rfcomm_services.services:
        print(f" - Service: {s.service_id.as_string()}")

    # Select target service (try 0000079A first, fallback to SPP 00001101)
    target_service = None
    for s in rfcomm_services.services:
        sid_str = s.service_id.as_string().lower()
        if "0000079a" in sid_str:
            target_service = s
            print("Selected OPO custom RFCOMM service!")
            break
            
    if not target_service and len(rfcomm_services.services) > 0:
        target_service = rfcomm_services.services[0]
        print(f"Selected fallback service: {target_service.service_id.as_string()}")
        
    if not target_service:
        print("No RFCOMM service available!")
        return

    socket = StreamSocket()
    print(f"Connecting to socket {target_service.connection_service_name}...")
    try:
        await socket.connect_async(target_service.connection_host_name, target_service.connection_service_name)
        print(" Connected to socket!")
    except Exception as e:
        print(f"Socket connection failed: {e}")
        return

    writer = DataWriter(socket.output_stream)
    reader = DataReader(socket.input_stream)
    reader.input_stream_options = InputStreamOptions.PARTIAL

    listener_task = asyncio.create_task(read_loop(reader))
    await asyncio.sleep(0.5)

    try:
        # Step 1: Send HELLO
        print("\n[Step 1] Sending HELLO...")
        writer.write_bytes(HELLO_PKT)
        await writer.store_async()
        print(f"-> TX: {' '.join(HELLO_PKT.hex().upper()[i:i+2] for i in range(0, len(HELLO_PKT.hex()), 2))}")
        
        await asyncio.sleep(1.8)

        # Step 2: Send REGISTER
        print("\n[Step 2] Sending REGISTER (Token B5 50 A0 69)...")
        writer.write_bytes(REGISTER_PKT)
        await writer.store_async()
        print(f"-> TX: {' '.join(REGISTER_PKT.hex().upper()[i:i+2] for i in range(0, len(REGISTER_PKT.hex()), 2))}")
        
        await asyncio.sleep(1.5)

        # Step 3: Query current state
        print("\n[Step 3] Querying ANC status...")
        writer.write_bytes(ANC_QUERY)
        await writer.store_async()
        print(f"-> TX: {' '.join(ANC_QUERY.hex().upper()[i:i+2] for i in range(0, len(ANC_QUERY.hex()), 2))}")

        await asyncio.sleep(1.5)

        # Step 4: Toggle to Normal Mode (ANC Off)
        print("\n[Step 4] Switching ANC to NORMAL mode (ANC Off)...")
        writer.write_bytes(ANC_OFF)
        await writer.store_async()
        print(f"-> TX: {' '.join(ANC_OFF.hex().upper()[i:i+2] for i in range(0, len(ANC_OFF.hex()), 2))}")

        await asyncio.sleep(2.0)

    except Exception as e:
        print(f"Communication error: {e}")
    finally:
        print("\nFinishing test...")
        listener_task.cancel()
        socket.close()

if __name__ == "__main__":
    asyncio.run(main())
