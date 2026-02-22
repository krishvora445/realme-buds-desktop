import asyncio
import sys
import uuid
import time
from winrt.windows.devices.bluetooth import BluetoothDevice
from winrt.windows.devices.bluetooth.rfcomm import RfcommServiceId
from winrt.windows.networking.sockets import StreamSocket
from winrt.windows.storage.streams import DataWriter, DataReader, InputStreamOptions

SPP_UUID = uuid.UUID("00001101-0000-1000-8000-00805F9B34FB")

AUTH_REQ = bytes.fromhex("524d56010000100101010101010101010101010101010104ea")
ANC_NORMAL = bytes.fromhex("524d56040200030205028c1b")
ANC_NOISE_CANCEL = bytes.fromhex("524d56040300030205019cde")
ANC_TRANSPARENT = bytes.fromhex("524d5604040003020503bc58")

async def read_loop(reader: DataReader):
    print("Started background listener...")
    while True:
        try:
            # Load up to 1024 bytes asynchronously; will unblock when data arrives
            count = await reader.load_async(1024)
            if count > 0:
                resp = reader.read_bytes(count)
                print(f"\n<- RECEIVED RAW: {bytes(resp).hex().upper()}")
            else:
                # Connection closed by remote
                print("\n<- Connection closed by remote")
                break
        except Exception as e:
            print(f"\nRead loop error: {e}")
            break

async def test_spp(mac_str):
    mac_int = int(mac_str.replace(":", ""), 16)
    print(f"Loading device {mac_str} ...")
    
    try:
        device = await BluetoothDevice.from_bluetooth_address_async(mac_int)
    except Exception as e:
        print(f"Error loading device: {e}")
        return
        
    if not device:
        print("Device not found! Make sure it's paired in Windows.")
        return
        
    print(f"Found {device.name}. Fetching RFCOMM services...")
    service_id = RfcommServiceId.from_uuid(SPP_UUID)
    
    try:
        res = await device.get_rfcomm_services_for_id_async(service_id)
        if not res.services or len(res.services) == 0:
            print("No SPP service found on this device!")
            return
            
        service = res.services[0]
        host = service.connection_host_name
        if host:
            print(f"Connecting to RFCOMM service on {host.display_name}...")
        else:
            print("Connecting to RFCOMM service...")
            
        socket = StreamSocket()
        await socket.connect_async(service.connection_host_name, service.connection_service_name)
        print("✅ Connected to SPP socket!")
    except Exception as e:
        print(f"Connection failed: {e}")
        return
        
    writer = DataWriter(socket.output_stream)
    reader = DataReader(socket.input_stream)
    reader.input_stream_options = InputStreamOptions.PARTIAL
    
    # Start the continuous read loop in the background
    listener_task = asyncio.create_task(read_loop(reader))
    
    # Give the listener a fraction of a second to start
    await asyncio.sleep(0.5)

    try:
        print("\nSending Auth Req...")
        writer.write_bytes(AUTH_REQ)
        await writer.store_async()
        print(f"-> {AUTH_REQ.hex().upper()}")
        
        # Wait to let response arrive and be printed by the listener
        await asyncio.sleep(2.0)
        
        print("\nSending ANC Normal Command (blindly)...")
        writer.write_bytes(ANC_NORMAL)
        await writer.store_async()
        print(f"-> {ANC_NORMAL.hex().upper()}")
        await asyncio.sleep(1.0)
        
        print("\nSending ANC Noise Canceling Command (blindly)...")
        writer.write_bytes(ANC_NOISE_CANCEL)
        await writer.store_async()
        print(f"-> {ANC_NOISE_CANCEL.hex().upper()}")
        await asyncio.sleep(1.0)
        
        print("\nSending ANC Transparent Command (blindly)...")
        writer.write_bytes(ANC_TRANSPARENT)
        await writer.store_async()
        print(f"-> {ANC_TRANSPARENT.hex().upper()}")
        await asyncio.sleep(2.0)
        
    except Exception as e:
        print(f"Write failed: {e}")
        
    print("\nClosing socket...")
    listener_task.cancel()
    try:
        socket.close()
    except:
        pass

if __name__ == "__main__":
    mac = input("Enter Classic Bluetooth MAC (e.g. 88:0E:85:46:18:C9): ").strip()
    if mac:
        try:
            asyncio.run(test_spp(mac))
        except KeyboardInterrupt:
            pass
