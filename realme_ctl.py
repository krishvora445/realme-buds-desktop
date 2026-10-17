import asyncio
import sys
from winsdk.windows.devices.bluetooth import BluetoothDevice
from winsdk.windows.networking.sockets import StreamSocket
from winsdk.windows.storage.streams import DataWriter, DataReader, InputStreamOptions

# Handshake packets
HELLO_PKT = bytes.fromhex("AA070000000123000012")
REGISTER_PKT = bytes.fromhex("AA0C0000008541050000B550A069")

# Fixed ANC Modes mapping:
# User verified on Realme Buds T310:
# Payload 01 = Normal Mode (ANC Off)
# Payload 04 = Noise Canceling
# Payload 02 = Transparency
MODES = {
    "1": ("Noise Canceling", bytes.fromhex("AA0A00000404400300010104")),
    "2": ("Transparency",    bytes.fromhex("AA0A00000404420300010102")),
    "3": ("Normal (Off)",     bytes.fromhex("AA0A00000404420300010101")),
}

# Queries
BATTERY_QUERY = bytes.fromhex("AA060000068200")
ANC_QUERY     = bytes.fromhex("AA070000048220000000")

async def read_loop(reader: DataReader):
    while True:
        try:
            count = await reader.load_async(1024)
            if count > 0:
                resp = reader.read_bytes(count)
                hex_str = bytes(resp).hex().upper()
                formatted_hex = " ".join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
                print(f"<- RX: {formatted_hex}")
            else:
                break
        except asyncio.CancelledError:
            break
        except Exception:
            break

async def send_command(mode_key: str, mac_str: str = "88:0E:85:46:18:C9"):
    mode_info = MODES.get(mode_key)
    if not mode_info:
        print(f"Unknown mode: '{mode_key}'. Available options:")
        print("  1 = Noise Canceling")
        print("  2 = Transparency")
        print("  3 = Normal (Off)")
        return False

    mode_name, mode_pkt = mode_info
    mac_int = int(mac_str.replace(":", ""), 16)

    print(f"Connecting to Realme Buds T310 ({mac_str})...")
    try:
        device = await BluetoothDevice.from_bluetooth_address_async(mac_int)
    except Exception as e:
        print(f"Bluetooth device lookup failed: {e}")
        return False

    if not device:
        print("Device not found. Make sure earbuds are connected to Windows.")
        return False

    rfcomm_services = await device.get_rfcomm_services_async()
    target_service = None
    for s in rfcomm_services.services:
        if "0000079a" in s.service_id.as_string().lower():
            target_service = s
            break
    if not target_service and len(rfcomm_services.services) > 0:
        target_service = rfcomm_services.services[0]

    if not target_service:
        print("No RFCOMM service found!")
        return False

    socket = StreamSocket()
    try:
        await socket.connect_async(target_service.connection_host_name, target_service.connection_service_name)
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

    print(" Connected!")

    writer = DataWriter(socket.output_stream)
    reader = DataReader(socket.input_stream)
    reader.input_stream_options = InputStreamOptions.PARTIAL

    listener = asyncio.create_task(read_loop(reader))
    await asyncio.sleep(0.2)

    try:
        # Step 1: Handshake
        print("Authenticating session...")
        writer.write_bytes(HELLO_PKT)
        await writer.store_async()
        await asyncio.sleep(1.2)

        writer.write_bytes(REGISTER_PKT)
        await writer.store_async()
        await asyncio.sleep(1.0)

        # Step 2: Send Mode command
        print(f"Switching ANC to: {mode_name}...")
        writer.write_bytes(mode_pkt)
        await writer.store_async()
        await asyncio.sleep(0.8)
        print(f" Successfully applied {mode_name}!")
        return True

    finally:
        listener.cancel()
        socket.close()

def print_help():
    print("""
Realme Buds Desktop Controller (realme_ctl.py)
----------------------------------------------
Usage:
  python realme_ctl.py <mode> [MAC_ADDRESS]

Modes:
  1, anc, nc      : Noise Canceling
  2, trans        : Transparency
  3, normal, off  : Normal Mode (ANC Off)

Interactive:
  python realme_ctl.py
""")

async def interactive():
    print_help()
    while True:
        try:
            choice = input("\nSelect mode (1=ANC, 2=Trans, 3=Normal, q=quit): ").strip().lower()
            if choice in ['q', 'quit', 'exit']:
                break
            if choice in ['1', 'anc', 'nc']:
                await send_command('1')
            elif choice in ['2', 'trans']:
                await send_command('2')
            elif choice in ['3', 'normal', 'off']:
                await send_command('3')
            else:
                print("Invalid choice!")
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        mapping = {
            '1': '1', 'anc': '1', 'nc': '1',
            '2': '2', 'trans': '2',
            '3': '3', 'normal': '3', 'off': '3'
        }
        if arg in ['-h', '--help']:
            print_help()
        elif arg in mapping:
            asyncio.run(send_command(mapping[arg]))
        else:
            print_help()
    else:
        asyncio.run(interactive())
