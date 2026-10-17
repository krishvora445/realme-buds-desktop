"""
Realme Buds T310 Desktop Controller
Modern Windows 11 GUI & System Tray Application for ANC Control.
"""

import os
import sys
import queue
import threading
import time
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk
import pystray

from realme_backend import RealmeBackend, MODES
from config_manager import load_config, save_config
from icon_generator import create_tray_icon, ensure_assets

# Configure CustomTkinter defaults
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ModernModeCard(ctk.CTkFrame):
    """Modern interactive card for selecting an ANC mode."""
    def __init__(self, master, mode_id: str, title: str, subtitle: str, icon_str: str,
                 accent_color: str, on_click, **kwargs):
        super().__init__(master, corner_radius=14, border_width=2, **kwargs)
        self.mode_id = mode_id
        self.title_text = title
        self.subtitle_text = subtitle
        self.icon_str = icon_str
        self.accent_color = accent_color
        self.on_click = on_click
        self.is_active = False
        self.is_busy = False

        self.default_bg = ("#2B2B36", "#212126")
        self.hover_bg = ("#363644", "#2A2A32")
        self.active_bg = ("#1F2937", "#1E222D")
        self.default_border = ("#3E3E4E", "#32323A")

        self.configure(fg_color=self.default_bg, border_color=self.default_border, cursor="hand2")

        # Layout
        self.grid_columnconfigure(1, weight=1)

        # Left Icon Frame
        self.icon_label = ctk.CTkLabel(
            self,
            text=icon_str,
            font=("Segoe UI Emoji", 26),
            width=50,
            height=50,
            corner_radius=12,
            fg_color=("#33333F", "#2A2A33")
        )
        self.icon_label.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=14, sticky="w")

        # Text Frame
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=("Segoe UI", 15, "bold"),
            anchor="w",
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=1, padx=(0, 10), pady=(14, 2), sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self,
            text=subtitle,
            font=("Segoe UI", 11),
            anchor="w",
            text_color="#A0A0AB"
        )
        self.subtitle_label.grid(row=1, column=1, padx=(0, 10), pady=(0, 14), sticky="w")

        # Right Status Pill
        self.badge = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 10, "bold"),
            corner_radius=10,
            width=76,
            height=24,
            fg_color="transparent",
            text_color="#FFFFFF"
        )
        self.badge.grid(row=0, column=2, rowspan=2, padx=(0, 16), pady=14, sticky="e")

        # Bind hover and click events across all children
        for w in (self, self.icon_label, self.title_label, self.subtitle_label, self.badge):
            w.bind("<Button-1>", lambda e: self.on_click(self.mode_id))
            w.bind("<Enter>", lambda e: self._on_hover(True))
            w.bind("<Leave>", lambda e: self._on_hover(False))

    def _on_hover(self, entering: bool):
        if self.is_active or self.is_busy:
            return
        if entering:
            self.configure(fg_color=self.hover_bg, border_color="#505060")
        else:
            self.configure(fg_color=self.default_bg, border_color=self.default_border)

    def set_state(self, active: bool, busy: bool = False):
        self.is_active = active
        self.is_busy = busy

        if busy:
            self.configure(
                fg_color=self.active_bg,
                border_color="#FF9F0A",
                border_width=2
            )
            self.badge.configure(
                text="APPLYING...",
                fg_color="#423000",
                text_color="#FFD60A"
            )
        elif active:
            self.configure(
                fg_color=self.active_bg,
                border_color=self.accent_color,
                border_width=2
            )
            self.badge.configure(
                text="ACTIVE",
                fg_color=self.accent_color,
                text_color="#FFFFFF"
            )
        else:
            self.configure(
                fg_color=self.default_bg,
                border_color=self.default_border,
                border_width=1
            )
            self.badge.configure(text="", fg_color="transparent")


class RealmeBudsApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = load_config()
        self.title("Realme Buds T310")
        self.geometry("440x620")
        self.minsize(420, 580)
        self.resizable(False, False)

        # Asset paths
        self.ico_path, self.png_path = ensure_assets()
        try:
            self.iconbitmap(self.ico_path)
        except Exception:
            pass

        # Thread-safe UI queue for dispatching from worker threads
        self.ui_queue: queue.Queue = queue.Queue()

        # Backend Bluetooth Worker
        self.backend = RealmeBackend(
            mac_address=self.config.get("mac_address", "88:0E:85:46:18:C9"),
            on_status=self._handle_backend_status
        )
        self.backend.start()

        # State tracking
        self.current_mode: str = self.config.get("last_mode", "1")
        self.target_mode: Optional[str] = None
        self.last_status_msg: str = "Ready"
        self.is_busy: bool = False

        # Build UI
        self._build_header()
        self._build_mode_selector()
        self._build_status_card()
        self._build_settings_drawer()
        self._build_footer()

        # Start periodic queue polling in the Tk main loop
        self.after(50, self._process_ui_queue)

        # Intercept window close (X) for minimize to tray
        self.protocol("WM_DELETE_WINDOW", self.on_close_button_clicked)

        # System Tray Icon
        self.tray_icon: Optional[pystray.Icon] = None
        self._init_system_tray()

        # Update initial active card
        self._update_card_states()

        # Check if start minimized
        if self.config.get("start_minimized", False):
            self.withdraw()

    # ================= UI BUILDERS =================

    def _build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 10))

        # Title & Subtitle in left column
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", fill="y")

        app_title = ctk.CTkLabel(
            title_box,
            text="Realme Buds T310",
            font=("Segoe UI", 20, "bold"),
            anchor="w",
            text_color="#FFFFFF"
        )
        app_title.pack(anchor="w")

        app_subtitle = ctk.CTkLabel(
            title_box,
            text="Desktop ANC Controller",
            font=("Segoe UI", 12),
            text_color="#8E8E93",
            anchor="w"
        )
        app_subtitle.pack(anchor="w")

        # Right status pill
        self.status_pill = ctk.CTkLabel(
            header_frame,
            text="READY",
            font=("Segoe UI", 11, "bold"),
            corner_radius=12,
            width=90,
            height=28,
            fg_color="#1E3A2F",
            text_color="#30D158"
        )
        self.status_pill.pack(side="right", pady=4)

    def _build_mode_selector(self):
        modes_container = ctk.CTkFrame(self, fg_color="transparent")
        modes_container.pack(fill="x", padx=24, pady=10)

        section_lbl = ctk.CTkLabel(
            modes_container,
            text="NOISE CONTROL MODES",
            font=("Segoe UI", 11, "bold"),
            text_color="#636366"
        )
        section_lbl.pack(anchor="w", pady=(0, 8))

        self.cards = {}

        card_defs = [
            ("1", "Noise Canceling", "Mutes ambient background noise", "🛡️", "#0A84FF"),
            ("2", "Transparency", "Hear environment & clear voices", "👂", "#FF9F0A"),
            ("3", "Normal (Off)", "Passive isolation with ANC disabled", "⭕", "#6C757D"),
        ]

        for mode_id, title, desc, icon, color in card_defs:
            card = ModernModeCard(
                modes_container,
                mode_id=mode_id,
                title=title,
                subtitle=desc,
                icon_str=icon,
                accent_color=color,
                on_click=self.request_mode
            )
            card.pack(fill="x", pady=6)
            self.cards[mode_id] = card

    def _build_status_card(self):
        self.status_card = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1C1C22", "#18181E"), border_width=1, border_color="#2C2C36")
        self.status_card.pack(fill="x", padx=24, pady=10)

        self.status_icon = ctk.CTkLabel(self.status_card, text="ℹ️", font=("Segoe UI Emoji", 14), width=30)
        self.status_icon.pack(side="left", padx=(10, 5), pady=8)

        self.status_text = ctk.CTkLabel(
            self.status_card,
            text="Connected • Ready to switch modes",
            font=("Segoe UI", 11),
            text_color="#A0A0AB",
            anchor="w"
        )
        self.status_text.pack(side="left", fill="x", expand=True, padx=5, pady=8)

    def _build_settings_drawer(self):
        self.settings_frame = ctk.CTkFrame(self, corner_radius=12, fg_color=("#22222A", "#1C1C22"), border_width=1, border_color="#2D2D38")
        self.settings_frame.pack(fill="x", padx=24, pady=8)

        # MAC Address row
        mac_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        mac_row.pack(fill="x", padx=14, pady=(12, 6))

        mac_lbl = ctk.CTkLabel(mac_row, text="Bluetooth MAC:", font=("Segoe UI", 12), text_color="#C7C7CC")
        mac_lbl.pack(side="left")

        self.mac_entry = ctk.CTkEntry(
            mac_row,
            width=160,
            height=28,
            font=("Consolas", 12),
            fg_color="#141418",
            border_color="#3A3A46"
        )
        self.mac_entry.insert(0, self.config.get("mac_address", "88:0E:85:46:18:C9"))
        self.mac_entry.pack(side="left", padx=(10, 8))

        save_btn = ctk.CTkButton(
            mac_row,
            text="Save",
            width=50,
            height=28,
            font=("Segoe UI", 11, "bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._save_mac_address
        )
        save_btn.pack(side="right")

        # Toggles row
        toggles_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        toggles_row.pack(fill="x", padx=14, pady=(4, 12))

        self.tray_switch = ctk.CTkCheckBox(
            toggles_row,
            text="Minimize to tray on close",
            font=("Segoe UI", 11),
            text_color="#A0A0AB",
            checkbox_width=18,
            checkbox_height=18,
            command=self._update_preferences
        )
        if self.config.get("minimize_to_tray", True):
            self.tray_switch.select()
        self.tray_switch.pack(side="left", pady=2)

        self.notify_switch = ctk.CTkCheckBox(
            toggles_row,
            text="Notifications",
            font=("Segoe UI", 11),
            text_color="#A0A0AB",
            checkbox_width=18,
            checkbox_height=18,
            command=self._update_preferences
        )
        if self.config.get("notify_on_change", True):
            self.notify_switch.select()
        self.notify_switch.pack(side="right", padx=(10, 0), pady=2)

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(10, 16), side="bottom")

        # Minimize to Tray button
        to_tray_btn = ctk.CTkButton(
            footer,
            text="Minimize to Tray",
            font=("Segoe UI", 12),
            fg_color="#2C2C36",
            hover_color="#3A3A46",
            height=32,
            command=self.hide_to_tray
        )
        to_tray_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        # Exit app button
        quit_btn = ctk.CTkButton(
            footer,
            text="Exit",
            font=("Segoe UI", 12),
            fg_color="#3A1C1C",
            hover_color="#542424",
            text_color="#FF453A",
            height=32,
            width=70,
            command=self.quit_app
        )
        quit_btn.pack(side="right", padx=(6, 0))

    # ================= BACKEND & STATE HANDLING =================

    def _process_ui_queue(self):
        """Poll queued updates on main thread."""
        try:
            while not self.ui_queue.empty():
                callback, args = self.ui_queue.get_nowait()
                callback(*args)
        except Exception as e:
            print(f"[UI Queue Error]: {e}")
        finally:
            self.after(50, self._process_ui_queue)

    def request_mode(self, mode_id: str):
        """User triggered a mode switch."""
        if self.is_busy:
            return
        self.target_mode = mode_id
        self.is_busy = True
        self._update_card_states()
        self.status_pill.configure(
            text="BUSY",
            fg_color="#3A3000",
            text_color="#FFD60A"
        )
        self.status_text.configure(text=f"Requesting {MODES[mode_id]['name']}...")
        self.backend.set_mode(mode_id)

    def _handle_backend_status(self, state: str, message: str, mode_id: Optional[str] = None):
        """Called from worker thread; put into thread-safe queue."""
        self.ui_queue.put((self._apply_status_update, (state, message, mode_id)))

    def _apply_status_update(self, state: str, message: str, mode_id: Optional[str]):
        self.last_status_msg = message

        if state == "BUSY":
            self.is_busy = True
            self.status_icon.configure(text="⏳")
            self.status_text.configure(text=message, text_color="#FFD60A")
            self.status_pill.configure(
                text="CONNECTING",
                fg_color="#3A3000",
                text_color="#FFD60A"
            )
            self._update_tray_icon(mode=mode_id or self.current_mode, state="BUSY")

        elif state == "SUCCESS":
            self.is_busy = False
            self.current_mode = mode_id or self.current_mode
            self.config["last_mode"] = self.current_mode
            save_config(self.config)

            now_str = datetime.now().strftime("%H:%M:%S")
            self.status_icon.configure(text="✅")
            self.status_text.configure(text=f"{message} ({now_str})", text_color="#30D158")
            self.status_pill.configure(
                text="CONNECTED",
                fg_color="#1E3A2F",
                text_color="#30D158"
            )
            self._update_card_states()
            self._update_tray_icon(mode=self.current_mode, state="SUCCESS")

            if self.config.get("notify_on_change", True) and self.tray_icon:
                try:
                    mode_name = MODES.get(self.current_mode, {}).get("name", "Active")
                    self.tray_icon.notify(
                        title="Realme Buds T310",
                        message=f"Mode active: {mode_name}"
                    )
                except Exception:
                    pass

        elif state == "ERROR":
            self.is_busy = False
            self.status_icon.configure(text="⚠️")
            self.status_text.configure(text=message, text_color="#FF453A")
            self.status_pill.configure(
                text="ERROR",
                fg_color="#3A1C1C",
                text_color="#FF453A"
            )
            self._update_card_states()
            self._update_tray_icon(mode=self.current_mode, state="ERROR")

    def _update_card_states(self):
        for mid, card in self.cards.items():
            if self.is_busy and mid == self.target_mode:
                card.set_state(active=False, busy=True)
            else:
                card.set_state(active=(mid == self.current_mode), busy=False)

    def _save_mac_address(self):
        new_mac = self.mac_entry.get().strip().upper()
        if len(new_mac) >= 12:
            self.config["mac_address"] = new_mac
            save_config(self.config)
            self.backend.mac_address = new_mac
            self.status_text.configure(text=f"Updated MAC address to {new_mac}", text_color="#30D158")

    def _update_preferences(self):
        self.config["minimize_to_tray"] = bool(self.tray_switch.get())
        self.config["notify_on_change"] = bool(self.notify_switch.get())
        save_config(self.config)

    # ================= SYSTEM TRAY =================

    def _init_system_tray(self):
        tray_img = create_tray_icon(mode=self.current_mode, state="IDLE")

        menu = pystray.Menu(
            pystray.MenuItem("Realme Buds T310", lambda: self.show_from_tray(), enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Noise Canceling",
                lambda icon, item: self.ui_queue.put((self.request_mode, ("1",))),
                checked=lambda item: self.current_mode == "1",
                radio=True
            ),
            pystray.MenuItem(
                "Transparency",
                lambda icon, item: self.ui_queue.put((self.request_mode, ("2",))),
                checked=lambda item: self.current_mode == "2",
                radio=True
            ),
            pystray.MenuItem(
                "Normal (Off)",
                lambda icon, item: self.ui_queue.put((self.request_mode, ("3",))),
                checked=lambda item: self.current_mode == "3",
                radio=True
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Controller", lambda icon, item: self.ui_queue.put((self.show_from_tray, ())), default=True),
            pystray.MenuItem("Exit", lambda icon, item: self.ui_queue.put((self.quit_app, ())))
        )

        mode_name = MODES.get(self.current_mode, {}).get("name", "Noise Control")
        tooltip = f"Realme Buds T310: {mode_name}"

        self.tray_icon = pystray.Icon("RealmeBudsT310", tray_img, tooltip, menu)

        # Run tray in daemon thread
        threading.Thread(target=self.tray_icon.run, daemon=True, name="TrayThread").start()

    def _update_tray_icon(self, mode: str, state: str):
        if not self.tray_icon:
            return
        try:
            new_img = create_tray_icon(mode=mode, state=state)
            self.tray_icon.icon = new_img
            mode_name = MODES.get(mode, {}).get("name", "Ready")
            self.tray_icon.title = f"Realme Buds T310: {mode_name}"
            self.tray_icon.update_menu()
        except Exception as e:
            print(f"[Tray Update Error]: {e}")

    def show_from_tray(self):
        """Bring window to front."""
        self.deiconify()
        self.state("normal")
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def hide_to_tray(self):
        """Minimize window to tray."""
        self.withdraw()

    def on_close_button_clicked(self):
        if self.config.get("minimize_to_tray", True):
            self.hide_to_tray()
        else:
            self.quit_app()

    def quit_app(self):
        """Clean shutdown."""
        try:
            self.backend.stop()
        except Exception:
            pass
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.destroy()
        sys.exit(0)


def main():
    app = RealmeBudsApp()
    app.mainloop()

if __name__ == "__main__":
    main()
