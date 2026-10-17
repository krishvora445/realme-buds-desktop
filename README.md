# Realme Buds T310 - Windows Desktop Controller & Protocol

A polished, modern Windows desktop application and system tray utility to control **Realme Buds T310** (and compatible BBK/Oppo/Realme wireless audio devices) directly from Windows without requiring the mobile app.

---

## 🎧 Features

- **Windows 11 Native Aesthetic**: Designed with CustomTkinter following Fluent Design dark mode styling with rounded interactive cards and accent highlights.
- **System Tray Resident**: Quick right-click context menu in the notification area for instantaneous mode changes without keeping the window open.
- **Real-Time Visual Feedback**: Color-coded badges and status pill reflecting current mode (Blue for Noise Canceling, Amber for Transparency, Silver for Normal).
- **Zero GUI Freezing**: Dedicated asynchronous worker thread runs RFCOMM sockets and OPOv1 auth handshakes via thread-safe message queues.
- **Automatic State Persistence**: Automatically remembers your device MAC address and preferred options in `config.json`.
- **Silent Background Launcher**: 1-click launch via `.vbs` or Desktop Shortcut with native app icon.

---

## 🚀 Quick Start

### 1. Requirements & Installation
Ensure you have Python 3.10+ installed on Windows. Install the required dependencies:
```bash
pip install -r requirements.txt
```

### 2. Launching the Desktop Application

- **Standard GUI**:
  ```bash
  python app.py
  ```
  *(Or double-click `run_app.bat`)*

- **Silent Tray Launch (No Console Window)**:
  Double-click `run_silent.vbs` or run:
  ```bash
  pythonw app.py
  ```

- **Create Windows Desktop Shortcut**:
  ```bash
  python create_shortcut.py
  ```
  This creates a shortcut titled `Realme Buds T310` directly on your Windows Desktop with the official app icon.

---

## 🎛️ Command-Line Interface (CLI)

For command-line or scripted usage, use [realme_ctl.py](file:///C:/Users/krish/Documents/Realme-buds-desktop/realme_ctl.py):

* **Switch to Noise Canceling**:
  ```bash
  python realme_ctl.py 1
  # or: python realme_ctl.py anc
  ```

* **Switch to Transparency Mode**:
  ```bash
  python realme_ctl.py 2
  # or: python realme_ctl.py trans
  ```

* **Switch to Normal Mode (ANC Off)**:
  ```bash
  python realme_ctl.py 3
  # or: python realme_ctl.py off
  ```

* **Interactive Mode**:
  ```bash
  python realme_ctl.py
  ```

---

## 🎯 Protocol Details & Reverse Engineering

The earbuds do **not** accept raw `RMV` (`52 4D 56`) packets over standard RFCOMM. 
Instead, they communicate using the proprietary **OPOv1 framing protocol** starting with `0xAA` over custom RFCOMM service UUID `0000079A-D102-11E1-9B23-00025B00A5A5`. 

Before any setting or ANC command is accepted, the earbuds require a mandatory **two-step authentication handshake**:
1. **`HELLO`** packet: `AA 07 00 00 00 01 23 00 00 12`
2. **`REGISTER`** packet containing the ecosystem authentication token `B5 50 A0 69`: `AA 0C 00 00 00 85 41 05 00 00 B5 50 A0 69`

Once authenticated, the earbuds acknowledge and immediately execute the ANC mode commands!

### Exact Mode Packets (Verified on Realme Buds T310)

| Function | Payload Value | Raw Hex Packet |
| :--- | :--- | :--- |
| **HELLO (Session Open)** | - | `AA 07 00 00 00 01 23 00 00 12` |
| **REGISTER (Auth Token)** | `B5 50 A0 69` | `AA 0C 00 00 00 85 41 05 00 00 B5 50 A0 69` |
| **ANC Mode: Noise Canceling** | `0x04` | `AA 0A 00 00 04 04 40 03 00 01 01 04` |
| **ANC Mode: Transparency** | `0x02` | `AA 0A 00 00 04 04 42 03 00 01 01 02` |
| **ANC Mode: Normal (Off)** | `0x01` | `AA 0A 00 00 04 04 42 03 00 01 01 01` |

---

## 📁 Repository Structure

- `app.py`: Main desktop app entry point.
- `realme_buds_gui.py`: CustomTkinter GUI + System Tray implementation.
- `realme_backend.py`: Asynchronous RFCOMM Bluetooth engine with WinRT integration.
- `config_manager.py`: Settings & persistent preferences manager (`config.json`).
- `icon_generator.py`: Generates high-DPI desktop & dynamic system tray icons.
- `create_shortcut.py`: Windows desktop shortcut generator.
- `run_app.bat` / `run_silent.vbs`: Launch scripts for regular and console-free execution.
- `realme_ctl.py`: Standalone CLI tool.
- `requirements.txt`: Python package dependencies.
