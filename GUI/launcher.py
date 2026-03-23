"""Startup launcher: scan for BLE devices and connect."""
import _thread
import tkinter as tk
from tkinter import ttk

from shared import mini_asyncio as asyncio
from shared.nanowinbt.scanner import NanoScanner
from GUI.controls import UIControls
from GUI.theme_manager import ThemeManager
from GUI.themed_messagebox import show_error
from GUI.widgets.helpers import theme_title_bar
from GUI.widgets.menubar import OwnerDrawnMenuBar
from GUI.widgets.themed_button import ThemedButton

_NAME_HINTS = {
    "DM40": "DM40",
    "EL15": "EL15",
    "ATK":  "EL15",   # Alientek OEM name used on EL15
}


def _guess_device_type(device) -> str | None:
    name = (device.name or "").upper()
    for prefix, dtype in _NAME_HINTS.items():
        if name.startswith(prefix):
            return dtype
    return None


class LauncherWindow(tk.Toplevel):
    """Startup scan window shown before any device-specific UI."""

    def __init__(self, master: tk.Tk, on_connect):
        super().__init__(master)
        self._on_connect_cb = on_connect

        self.title("DM40GUI — Select Device")
        self.resizable(False, False)
        self.wm_geometry("520x380")

        self.style = ttk.Style(self)
        self._theme_manager = ThemeManager(self, self.style, self._apply_theme)
        initial_theme = self._theme_manager.get_active_theme()
        self.ui = UIControls(self, self.style, theme=initial_theme)
        theme_title_bar(self, border_color=initial_theme.outline, caption_color=initial_theme.bg)

        self._devices: list = []
        self._device_index_by_address: dict[str, int] = {}
        self._scan_in_progress = False
        self._scan_generation = 0
        self._scan_cancel = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_theme(self, theme) -> None:
        self.ui.use_theme(theme)
        theme_title_bar(self, border_color=theme.outline, caption_color=theme.bg)

    def _build_ui(self) -> None:
        self._menu_bar = OwnerDrawnMenuBar(
            self,
            menus=[
                ("File", [("Exit", self._on_close)]),
                ("Themes", []),
            ],
            theme_manager=self._theme_manager,
            on_theme=self._apply_theme,
        )
        self._menu_bar.pack(fill=tk.X)

        tk.Label(
            self,
            text="Select a Bluetooth device",
            font=("Segoe UI", 13, "bold"),
        ).pack(fill="x", padx=12, pady=8)

        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=12)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self._device_listbox = tk.Listbox(
            list_frame,
            height=10,
            exportselection=False,
            activestyle="none",
            highlightthickness=2,
            relief="flat",
        )
        self._device_listbox.grid(row=0, column=0, sticky="nsew")
        self._device_listbox.bind("<Double-Button-1>", lambda _: self._on_connect())

        sb = ttk.Scrollbar(list_frame, orient="vertical",
                           command=self._device_listbox.yview,
                           style="Arrowless.Vertical.TScrollbar")
        sb.grid(row=0, column=1, sticky="ns")
        self._device_listbox.configure(yscrollcommand=sb.set)

        self._status_var = tk.StringVar(value="Click Scan to find devices")
        tk.Label(self, textvariable=self._status_var, anchor="w").pack(
            fill="x", padx=12, pady=(4, 0)
        )

        btn_row = tk.Frame(self)
        btn_row.pack(fill="x", padx=12, pady=(8, 12))
        ThemedButton(btn_row, text="Scan", command=self.scan_devices).pack(side=tk.LEFT)
        ThemedButton(btn_row, text="Connect", command=self._on_connect).pack(side=tk.RIGHT)

    def scan_devices(self) -> None:
        if self._scan_in_progress:
            return
        if NanoScanner.radio_state() == "off":
            msg = "Bluetooth radio is OFF. Turn Bluetooth on and try again."
            self._status_var.set(msg)
            show_error(self, "Scan", msg, theme=(self.ui.theme.bg, self.ui.theme.outline))
            return
        self._scan_generation += 1
        scan_id = self._scan_generation
        self._scan_in_progress = True
        self._scan_cancel = None
        self._devices = []
        self._device_index_by_address.clear()
        self._device_listbox.delete(0, tk.END)
        self._status_var.set("Scanning …")
        _thread.start_new_thread(self._scan_worker, (scan_id,))

    def _scan_worker(self, scan_id: int) -> None:
        def on_device(device) -> None:
            self.after(0, self._scan_add_device, scan_id, device)

        def register_cancel(cancel_scan) -> None:
            if scan_id == self._scan_generation:
                self._scan_cancel = cancel_scan
            else:
                cancel_scan()

        try:
            devices = asyncio.run(
                NanoScanner.discover(
                    scanning_mode="active",
                    on_device=on_device,
                    timeout=3.0,
                    on_cancel_register=register_cancel,
                    require_radio_check=False,
                )
            )
        except Exception as exc:
            self.after(0, lambda: self._scan_done(scan_id, [], exc))
            return
        self.after(0, lambda: self._scan_done(scan_id, devices or [], None))

    def _scan_add_device(self, scan_id: int, device) -> None:
        if scan_id != self._scan_generation:
            return
        addr = device.address
        if not addr:
            return
        name = device.name or "Unknown"
        existing = self._device_index_by_address.get(addr)
        if existing is not None:
            self._devices[existing].name = device.name
            desired = f"{name} ({addr})"
            if name != "Unknown" and self._device_listbox.get(existing) != desired:
                self._device_listbox.delete(existing)
                self._device_listbox.insert(existing, desired)
            return
        self._device_index_by_address[addr] = len(self._devices)
        self._devices.append(device)
        self._device_listbox.insert(tk.END, f"{name} ({addr})")

    def _scan_done(self, scan_id: int, devices: list, exc) -> None:
        if scan_id != self._scan_generation:
            return
        self._scan_in_progress = False
        self._scan_cancel = None
        if exc is not None:
            self._status_var.set("Scan failed")
            show_error(self, "Scan", f"BLE scan failed: {exc!r}",
                       theme=(self.ui.theme.bg, self.ui.theme.outline))
            return
        for device in devices:
            self._scan_add_device(scan_id, device)
        count = len(self._devices)
        self._status_var.set(f"Found {count} device{'s' if count != 1 else ''}")

    def _on_connect(self) -> None:
        sel = self._device_listbox.curselection()
        if not sel:
            show_error(self, "Connect", "Select a device from the list.",
                       theme=(self.ui.theme.bg, self.ui.theme.outline))
            return
        device = self._devices[sel[0]]
        self._on_connect_cb(device, _guess_device_type(device))

    def _on_close(self) -> None:
        self.master.destroy()
