# Realme Buds T310 - Desktop Control Reverse Engineering

This repository contains our deep-dive attempts to reverse engineer the Bluetooth protocol for the **Realme Buds T310** to allow controlling the Active Noise Canceling (ANC) modes directly from a Windows desktop (specifically to access "Normal" mode, which Realme locked behind their mobile app).

Despite decompiling the `Realme Link` Android APK, extracting the exact proprietary packet structure, and writing multiple native payload injectors, **we have hit a wall and are looking for help.**

---

## 🛑 The Goal
To send a command from a Windows PC to the Realme Buds T310 to switch ANC modes:
- Noise Canceling
- Normal (ANC Off, Transparency Off)
- Transparent

## 🔍 What We Found (The Protocol)
By decompiling the Realme Link app (specifically `SimpleSpp.java`, `VoiceReductionType.java`, etc.), we confirmed the earbuds use **Classic Bluetooth SPP (Serial Port Profile)** for command transmission.

### 1. The Packet Format: `RMV`
The protocol uses a custom `RMV` header.
Format: `0x52 0x4D 0x56` (`RMV`) + Command ID (1 byte) + Sequence (1 byte) + Payload Length (2 bytes) + Payload + CRC16 Checksum (2 bytes)

### 2. The HMAC-SHA256 Handshake
Before accepting ANC commands, the earbuds require a cryptographic handshake based on a hardcoded string key: `"hmac_key"`.
1. App sends an Auth Request (Cmd ID `0x01`) containing 16 random bytes (App Random).
2. Earbuds respond (Cmd ID `0x02`) with their own 16 random bytes *and* a 32-byte HMAC-SHA256 hash of the App Random.
3. App calculates the HMAC locally; if matched, it responds with an HMAC-SHA256 of the Earbuds' random bytes.
4. Connection is considered "Authenticated".

### 3. The ANC Commands (Cmd ID `0x04`)
Once authenticated, ANC modes are changed using Command ID `0x04` with the payload format: `0x02` (Set), `0x05` (Settings Key > ANC Status), followed by the mode byte.
- **Normal Mode:** `02 05 02`
- **Noise Canceling Mode:** `02 05 01`
- **Transparent Mode:** `02 05 03`

Precalculated `RMV` packet for Normal mode (assuming Seq `02`):
`52 4D 56 04 02 00 03 02 05 02 8C 1B`

---

## 🛠️ What We Tried (And Where It Fails)

### Attempt 1: Standard Python Sockets (socket.AF_BTH)
- **Code:** `realme_test.py`
- **Issue:** Windows completely blocks `socket.AF_BTH` in Python unless explicitly built for it. Resulted in `AttributeError`.

### Attempt 2: PySerial over Virtual COM Ports
- **Code:** `realme_test_com.py` and `realme_test_com_blind.py`
- **Approach:** Looping through Windows "Standard Serial over Bluetooth link" COM ports manually to send the initialization header.
- **Fail Reason:** No port responded. PuTTY also showed them as disconnected or locked. Windows COM port mappings for Bluetooth are notoriously unreliable for outgoing master commands.

### Attempt 3: BLE (Bluetooth Low Energy) GATT Service
- **Code:** `realme_test_ble.py`, `realme_test_ble_final.py`, `realme_test_ble_raw.py`, `realme_test_ble_oppo.py`
- **Approach:** Scanning the BLE MAC `88:0E:85:46:18:9C` revealed a custom Vendor service `000008A4-0000-1000-8000-00805f9b34fb`. We used the `bleak` library to connect.
- **Fail Reason:** We successfully connected and subscribed to `0002` (Notify). But writing the RMV packets (or raw payloads, or OPPO `0xAA` wrapped payloads) to `0001` (Write) yielded zero response. We suspect `0x08A4` on BLE is only for Google Fast Pair or finding the earbuds, not for SPP command routing.

### Attempt 4: Native Windows WinRT RFCOMM (SPP) API
- **Code:** `realme_test_winrt_spp.py`
- **Approach:** Bypassing COM ports entirely, we used Microsoft's native `windows.devices.bluetooth.rfcomm` WinRT APIs via `winrt` bindings to directly open the SPP socket to the Classic Bluetooth MAC `88:0E:85:46:18:C9`.
- **Result:** **Connection SUCCESS.** The script natively connected to the SPP stream socket!
- **The Wall:** Even with a fully open socket and a background asynchronous listening task, sending the exact `RMV` 16-byte random authentication init packet **yields absolutely no response**. We aggressively blind-fired the ANC command bytes immediately after, and still nothing. The buds drop the data silently.

---

## 🆘 Why Did The WinRT SPP Script Fail? (Looking for help!)

This is where we are stuck. The `InputStream` remains utterly silent after we write the perfectly constructed RMV auth packet to the `OutputStream`.
Possibilities:
1. **Flow Control / Handshake:** Is Windows RFCOMM missing a specific DTR/RTS signal required by Airoha chipsets to begin receiving?
2. **Obfuscation / Protocol Version:** Did Realme change the protocol header from `RMV` (`52 4D 56`) to something else for newer firmware?
3. **App Exclusivity Lock:** Are the earbuds "locked" uniquely to the phone's MAC address once paired via Realme Link?
4. **Different Service UUID:** Is there a hidden custom UUID for the Airoha SPP profile that isn't `00001101...`?

## Files in this Repo
- `realme_link_decompiled_headset/`: Key decompiled java classes from Realme Link handling `SimpleSpp` and `BTManager`.
- `realme_test_winrt_spp.py`: Our best, native connection script that connects but gets no response.
- `realme_test_ble*.py`: The failed BLE architecture tests.

**If you have experience with Airoha Bluetooth reverse engineering or Android RFCOMM captures, please reach out! A Bluetooth HCI Snoop log from an Android device successfully talking to these earbuds might be the final piece of the puzzle.**
