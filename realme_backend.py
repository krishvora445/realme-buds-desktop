"""
Realme Buds Bluetooth Backend Controller
Communicates with Realme Buds T310 (and compatible BBK/Oppo/Realme devices)
via Windows WinRT RFCOMM socket over service UUID 0000079a-d102-11e1-9b23-00025b00a5a5.
"""

import asyncio
import threading
import queue
import time
from typing import Optional, Callable

from winsdk.windows.devices.bluetooth import BluetoothDevice
from winsdk.windows.networking.sockets import StreamSocket
from winsdk.windows.storage.streams import DataWriter, DataReader, InputStreamOptions

# Framing & Handshake packets for OPOv1 framing
HELLO_PKT = bytes.fromhex("AA070000000123000012")
REGISTER_PKT = bytes.fromhex("AA0C0000008541050000B550A069")

# Fixed ANC Modes mapping:
# 1 = Noise Canceling
# 2 = Transparency
# 3 = Normal (ANC Off)
MODES = {
    "1": {
        "id": "1",
        "name": "Noise Canceling",
        "short_name": "ANC",
        "description": "Blocks ambient noise for maximum focus",
        "packet": bytes.fromhex("AA0A00000404400300010104"),
        "color": "#0A84FF",  # iOS/Win11 blue accent
    },
    "2": {
        "id": "2",
        "name": "Transparency",
        "short_name": "Transparency",
        "description": "Hear ambient sounds and nearby voices",
        "packet": bytes.fromhex("AA0A00000404420300010102"),
        "color": "#FF9F0A",  # Vibrant amber/orange
    },
    "3": {
        "id": "3",
        "name": "Normal (Off)",
        "short_name": "Normal",
        "description": "Standard passive audio with ANC turned off",
        "packet": bytes.fromhex("AA0A00000404420300010101"),
        "color": "#8E8E93",  # Neutral silver/slate
    },
}

class RealmeBackend:
    def __init__(self, mac_address: str = "88:0E:85:46:18:C9", on_status: Optional[Callable] = None):
        self.mac_address = mac_address
        self.on_status = on_status
        self.current_mode: Optional[str] = None
        self._cmd_queue: queue.Queue = queue.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._is_busy = False

    def start(self):
        """Starts the background worker thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="RealmeWorkerThread", daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the worker thread."""
        self._running = False
        if self._cmd_queue:
            self._cmd_queue.put(None)

    def _notify(self, state: str, message: str, mode_id: Optional[str] = None):
        """Invoke callback safely."""
        if self.on_status:
            try:
                self.on_status(state, message, mode_id)
            except Exception as e:
                print(f"[Backend Error in Callback]: {e}")

    def set_mode(self, mode_id: str):
        """Queue a request to switch ANC mode."""
        if mode_id not in MODES:
            self._notify("ERROR", f"Invalid mode key: {mode_id}")
            return
        self._cmd_queue.put(mode_id)

    def _run_loop(self):
        """Target for worker thread, runs asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._worker())

    async def _worker(self):
        while self._running:
            try:
                # Wait for command from queue without blocking the event loop
                mode_id = await asyncio.to_thread(self._cmd_queue.get)
                if mode_id is None:
                    break

                # Discard older queued items if user clicked multiple times quickly
                while not self._cmd_queue.empty():
                    next_item = self._cmd_queue.get_nowait()
                    if next_item is not None:
                        mode_id = next_item
                    else:
                        return

                self._is_busy = True
                await self._execute_switch(mode_id)
                self._is_busy = False
            except Exception as e:
                self._is_busy = False
                self._notify("ERROR", f"Worker error: {str(e)}")

    async def _execute_switch(self, mode_id: str):
        mode_info = MODES[mode_id]
        mode_name = mode_info["name"]
        mode_pkt = mode_info["packet"]
        mac_str = self.mac_address.strip().upper()

        self._notify("BUSY", f"Connecting to {mac_str}...", mode_id)
        
        try:
            mac_int = int(mac_str.replace(":", ""), 16)
        except ValueError:
            self._notify("ERROR", f"Invalid MAC address format: '{mac_str}'", mode_id)
            return False

        device = None
        for attempt in range(2):
            try:
                device = await BluetoothDevice.from_bluetooth_address_async(mac_int)
                if device:
                    break
            except Exception as e:
                err_str = str(e)
                if attempt == 0 and ("-2147020577" in err_str or "not ready" in err_str.lower()):
                    await asyncio.sleep(1.0)
                    continue
                if "-2147020577" in err_str or "not ready" in err_str.lower():
                    self._notify("ERROR", "Buds are disconnected or sleeping. Please reconnect them in Windows Settings.", mode_id)
                else:
                    self._notify("ERROR", f"Bluetooth lookup error: {e}", mode_id)
                return False

        if not device:
            self._notify("ERROR", "Buds not found. Please connect them in Windows Bluetooth Settings.", mode_id)
            return False

        try:
            rfcomm_services = await device.get_rfcomm_services_async()
        except Exception as e:
            self._notify("ERROR", f"Failed to get RFCOMM services: {e}", mode_id)
            return False

        target_service = None
        for s in rfcomm_services.services:
            if "0000079a" in s.service_id.as_string().lower():
                target_service = s
                break
        if not target_service and len(rfcomm_services.services) > 0:
            target_service = rfcomm_services.services[0]

        if not target_service:
            self._notify("ERROR", "No compatible RFCOMM service found on device.", mode_id)
            return False

        socket = StreamSocket()
        self._notify("BUSY", "Establishing RFCOMM socket...", mode_id)

        try:
            await socket.connect_async(target_service.connection_host_name, target_service.connection_service_name)
        except Exception as e:
            self._notify("ERROR", f"Connection failed: {e}. Check if earbuds are turned on.", mode_id)
            return False

        writer = DataWriter(socket.output_stream)
        reader = DataReader(socket.input_stream)
        reader.input_stream_options = InputStreamOptions.PARTIAL

        async def read_sink():
            while True:
                try:
                    count = await reader.load_async(1024)
                    if count > 0:
                        _ = reader.read_bytes(count)
                    else:
                        break
                except asyncio.CancelledError:
                    break
                except Exception:
                    break

        sink_task = asyncio.create_task(read_sink())
        await asyncio.sleep(0.15)

        try:
            self._notify("BUSY", "Authenticating session...", mode_id)
            writer.write_bytes(HELLO_PKT)
            await writer.store_async()
            await asyncio.sleep(1.1)

            writer.write_bytes(REGISTER_PKT)
            await writer.store_async()
            await asyncio.sleep(0.9)

            self._notify("BUSY", f"Applying {mode_name}...", mode_id)
            writer.write_bytes(mode_pkt)
            await writer.store_async()
            await asyncio.sleep(0.7)

            self.current_mode = mode_id
            self._notify("SUCCESS", f"Switched to {mode_name}", mode_id)
            return True
        except Exception as e:
            self._notify("ERROR", f"Send command failed: {e}", mode_id)
            return False
        finally:
            sink_task.cancel()
            try:
                socket.close()
            except Exception:
                pass
