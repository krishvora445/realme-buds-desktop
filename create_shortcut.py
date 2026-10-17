"""
Desktop Shortcut Creator for Realme Buds Controller
Creates a Windows Desktop shortcut with icon for 1-click silent launch.
"""

import os
import sys

def create_desktop_shortcut():
    try:
        import win32com.client
    except ImportError:
        print("win32com not available. Skipping shortcut creation.")
        return

    here = os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(desktop, "Realme Buds T310.lnk")
    icon_path = os.path.join(here, "assets", "app_icon.ico")
    vbs_path = os.path.join(here, "run_silent.vbs")

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = "wscript.exe"
    shortcut.Arguments = f'"{vbs_path}"'
    shortcut.WorkingDirectory = here
    if os.path.exists(icon_path):
        shortcut.IconLocation = f"{icon_path},0"
    shortcut.Description = "Realme Buds T310 Controller"
    shortcut.Save()
    print(f"Created desktop shortcut: {shortcut_path}")

if __name__ == "__main__":
    create_desktop_shortcut()
