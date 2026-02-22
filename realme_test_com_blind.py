import serial
import serial.tools.list_ports
import time

# Pre-calculated RMV packets
# 1. Auth Request (Random: 16 bytes of 0x01)
# 52 4D 56 01 00 00 10 01010101010101010101010101010101 [CRC16: 04 EA]
AUTH_REQ = bytes.fromhex("524d56010000100101010101010101010101010101010104ea")

# 2. ANC Normal Mode
# 52 4D 56 04 02 00 03 02 05 02 [CRC16: 8C 1B]
ANC_NORMAL = bytes.fromhex("524d56040200030205028c1b")

# 3. ANC Noise Canceling Mode
# 52 4D 56 04 03 00 03 02 05 01 [CRC16: 9C DE]
ANC_NOISE_CANCEL = bytes.fromhex("524d56040300030205019cde")

# 4. ANC Transparent Mode
# 52 4D 56 04 04 00 03 02 05 03 [CRC16: BC 58]
ANC_TRANSPARENT = bytes.fromhex("524d5604040003020503bc58")

def main():
    print("Realme SPP COM Port Tester")
    print("Available COM Ports:")
    ports = serial.tools.list_ports.comports()
    for port, desc, hwid in sorted(ports):
        print(f"[{port}] {desc}")
        
    com_port = input("\nEnter the COM port to use (e.g., COM3): ").strip()
    if not com_port:
        return
        
    try:
        # Open port with standard fast baudrate, no flow control
        print(f"\nOpening {com_port}...")
        ser = serial.Serial(com_port, 115200, timeout=1, write_timeout=1)
        print("✅ Port Opened!")
        
        # Give it a second to settle
        time.sleep(1)
        
        print("\nSending Auth Packet (blindly)...")
        ser.write(AUTH_REQ)
        print(f"-> {AUTH_REQ.hex().upper()}")
        
        # We don't care about the response for this test, just blast the ANC command
        time.sleep(1)
        
        print("\nSending ANC Normal Command...")
        ser.write(ANC_NORMAL)
        print(f"-> {ANC_NORMAL.hex().upper()}")
        time.sleep(1)
        
        print("\nSending ANC Noise Canceling Command...")
        ser.write(ANC_NOISE_CANCEL)
        print(f"-> {ANC_NOISE_CANCEL.hex().upper()}")
        time.sleep(1)
        
        print("\nTest completed. Did the earbuds beep or change modes?")
        
        # Read anything the earbuds sent back just in case
        while ser.in_waiting > 0:
            resp = ser.read(ser.in_waiting)
            print(f"<- Received: {resp.hex().upper()}")
            
        ser.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
