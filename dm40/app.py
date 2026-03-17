"""DM40 Tkinter application."""

import _thread
import time
import tkinter as tk
from tkinter import ttk

from . import mini_asyncio as asyncio

from dm40.types import ThemePalette
from GUI.controls import UIControls
from GUI.theme_manager import ThemeManager
from GUI.themed_messagebox import show_error
from GUI.widgets.autoscrollbar import AutoScrollbar
from GUI.widgets.find_popup import FindPopup
from GUI.widgets.helpers import ensure_dpi_awareness, theme_title_bar
from GUI.widgets.menubar import MENU_UP, MenuDropdown, OwnerDrawnMenuBar
from GUI.widgets.themed_button import ThemedButton
from GUI.widgets.waveform_view import WaveformView

from .ble_worker import BleWorker
from .nanowinbt.scanner import NanoScanner
from .parsing import MODEL, Measurement, parse_device_status, parse_measurement_for_ui
from .protocol_constants import (
    COMMAND_CYCLE_GROUPS,
    COMMAND_KIND_LABELS,
    COMMAND_KIND_TO_GROUP,
    FLAG_INFO,
    MOMENTARY_COMMANDS,
    RANGE_CYCLE_GROUPS,
    RANGE_KIND_TO_GROUP,
    TOGGLE_COMMANDS,
    UNIT_TO_BASE,
)

_TOGGLE_COMMANDS_MAP = {label: (c_on, c_off) for label, c_on, c_off in TOGGLE_COMMANDS}
_RANGE_ITEMS_BY_KIND: dict[str, list[tuple[str, int]]] = {}
for _flag, (_kind_name, _rng) in FLAG_INFO.items():
    _RANGE_ITEMS_BY_KIND.setdefault(_kind_name, []).append((_rng, _flag))


def _build_command_packet(cmd_prefix: bytes) -> bytes:
    checksum = (-sum(cmd_prefix)) & 0xFF
    return b"%b%c" % (cmd_prefix, checksum)


class DM40App(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_dpi_awareness()

        self._start_time = time.monotonic()
        self._title_base = "DM40"
        self.title(self._title_base)
        self.minsize(916, 650)
        self.wm_geometry("916x650")

        self.style = ttk.Style(self)

        self._theme_manager = ThemeManager(self, self.style, self._apply_theme)
        initial_theme = self._theme_manager.get_active_theme()
        self.ui = UIControls(self, self.style, theme=initial_theme)
        theme_title_bar(
            self,
            border_color=initial_theme.outline,
            caption_color=initial_theme.bg,
        )

        self._worker: BleWorker | None = None
        self._last_trace_key: int | None = None
        self._last_device_status: tuple = (0, False, False, False)
        self._devices: list = []
        self._device_index_by_address: dict[str, int] = {}
        self._scan_in_progress = False
        self._scan_generation = 0
        self._scan_cancel = None
        self._mode_buttons: list[ttk.Button | ttk.Checkbutton] = []
        self._range_button: ttk.Button | None = None
        self._range_menu: MenuDropdown | None = None
        self._toggle_vars: dict[str, tk.BooleanVar] = {
            label: tk.BooleanVar(value=False)
            for label in ("AUTO", "HOLD", "CAP")
        }
        self._cycle_groups: dict = {}
        self._last_base_mode_flag: int | None = None
        self._last_measurement: Measurement | None = None
        self._is_connected = False

        self._stats_count = 0
        self._stats_sum = 0.0
        self._stats_min = 0.0
        self._stats_max = 0.0

        self._build_ui()
        self.bind_all("<Key-p>", self._toggle_wave_pause)
        self.bind_all("<Control-s>", self._save_wave_csv)
        self.bind_all("<Key-r>", self._toggle_wave_record)
        self.bind_all("<Control-c>", self._copy_reading)

    def _toggle_wave_pause(self, _event=None) -> None:
        self._wave_view.toggle_pause()
        self._refresh_status_bar()

    def _copy_reading(self, _event=None) -> None:
        source = _event.widget if _event is not None else self.focus_get()
        if isinstance(source, (tk.Text, tk.Entry, ttk.Entry)):
            return

        m = self._last_measurement
        if not m or m.kind == "---":
            return
        unit = f" {m.display_unit}" if m.display_unit else ""
        self.clipboard_clear()
        self.clipboard_append(f"{m.value_str}{unit}")

    _CSV_DIR = __compiled__.containing_dir if '__compiled__' in globals() else __file__.rsplit('\\', 2)[0]  # type: ignore[name-defined]

    def _csv_path(self, prefix: str) -> str:
        return f"{self._CSV_DIR}\\{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.csv"

    def _save_wave_csv(self, _event=None) -> None:
        self._wave_view.save_buffer_csv(self._csv_path("DM40"))

    def _toggle_wave_record(self, _event=None) -> None:
        if self._wave_view.recording:
            self._wave_view.stop_recording()
        else:
            self._wave_view.toggle_recording(self._csv_path("DM40_rec"))
        self._refresh_status_bar()

    def _clear_capture_data(self) -> None:
        self._wave_view.clear()
        self._raw_text.configure(state="normal")
        self._raw_text.delete("1.0", "end")
        self._raw_text.configure(state="disabled")
        self._last_trace_key = None
        self._stats_count = 0
        self._stats_sum = 0.0
        self._stats_min = 0.0
        self._stats_max = 0.0
        self._stats_var.set("")
        self._refresh_status_bar()

    def _build_ui(self) -> None:
        self._menu_bar = OwnerDrawnMenuBar(
            self,
            menus=[
                (
                    "File",
                    [
                        ("Save Buffer", self._save_wave_csv),
                        ("Record", self._toggle_wave_record),
                        "separator",
                        ("Clear", self._clear_capture_data),
                        "separator",
                        ("Exit", self._on_close),
                    ],
                ),
                ("Themes", []),
            ],
            theme_manager=self._theme_manager,
            on_theme=self._apply_theme,
        )
        self._menu_bar.pack(fill=tk.X)
        self._menu_bar.grid_columnconfigure(2, weight=1)

        root = tk.Frame(self, padx=12, pady=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)

        self._model_var = tk.StringVar(value=MODEL.model_name)
        tk.Label(
            self._menu_bar, textvariable=self._model_var, font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=3, sticky="e")
        self._runtime_var = tk.StringVar(value="")
        tk.Label(self._menu_bar, textvariable=self._runtime_var).grid(
            row=0, column=4, sticky="w", padx=(0, 0)
        )
        self._icons_var = tk.StringVar(value="")
        tk.Label(self._menu_bar, textvariable=self._icons_var).grid(
            row=0, column=5, sticky="e", padx=(0, 0)
        )
        self._battery_label = tk.Label(
            self._menu_bar,
            text="",
            font=("Consolas", 10),
        )
        self._battery_label.grid(row=0, column=6, sticky="e", padx=(0, 8))

        self._status_var = tk.StringVar(value="Disconnected")
        mid = tk.Frame(root)
        mid.grid(row=1, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=3)

        reading = tk.Frame(mid)
        reading.grid(row=0, column=0, sticky="ew")
        reading.columnconfigure(0, weight=1)

        self._mode_var = tk.StringVar(value="---")
        tk.Label(
            reading, textvariable=self._mode_var, font=("Segoe UI", 12, "bold")
        ).grid(row=0, column=0, sticky="w")

        self._value_label = ttk.Label(
            reading,
            text="---",
            font=("Cascadia Mono", 44, "bold"),
            style="DM40.BigValue.TLabel",
            width=12,
            anchor="e",
        )

        self._value_label.grid(row=1, column=0, sticky="w")

        self._aux_var = tk.StringVar(value="")
        tk.Label(reading, textvariable=self._aux_var, font=("Segoe UI", 11)).grid(
            row=2, column=0, columnspan=2, sticky="w"
        )

        self._wave_view = WaveformView(mid, colors=self.ui.theme, capacity=600)
        self._wave_view.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        mid.rowconfigure(1, weight=1)

        self._stats_var = tk.StringVar(value="")
        tk.Label(mid, textvariable=self._stats_var, font=("Consolas", 10),
                 anchor="w").grid(row=2, column=0, sticky="ew", pady=(0, 10))

        raw_frame = tk.Frame(root)
        raw_frame.grid(row=2, column=0, sticky="nsew")
        raw_frame.columnconfigure(0, weight=1)
        raw_frame.rowconfigure(1, weight=1)
        root.rowconfigure(2, weight=1)

        tk.Label(raw_frame, text="Raw packets:").grid(row=0, column=0, sticky="w")

        self._raw_text = tk.Text(
            raw_frame,
            wrap="none",
            height=10,
            relief="flat",
            highlightthickness=2,
            undo=False,
            maxundo=0,
            autoseparators=False
        )
        self._raw_text.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        yscroll = AutoScrollbar(
            raw_frame,
            orient="vertical",
            command=self._raw_text.yview,
            style="Arrowless.Vertical.TScrollbar",
        )
        yscroll.grid(row=1, column=1, sticky="ns", pady=(6, 0))
        self._raw_text.configure(yscrollcommand=yscroll.set)
        self._raw_text.configure(state="disabled")

        device_panel = tk.Frame(raw_frame)
        device_panel.grid(row=0, column=2, rowspan=2, sticky="nsw", padx=(12, 0))
        device_panel.rowconfigure(1, weight=1)
        device_panel.columnconfigure(0, weight=0)
        device_panel.columnconfigure(1, weight=1)
        device_panel.columnconfigure(2, weight=0)

        tk.Label(device_panel, text="Devices:").grid(row=0, column=0, sticky="w")
        status_label = tk.Label(device_panel, textvariable=self._status_var)
        status_label.grid(row=0, column=1, columnspan=2, sticky="e")
        self._device_listbox = tk.Listbox(
            device_panel,
            height=10,
            width=58,
            exportselection=False,
            activestyle="none",
            highlightthickness=2,
            relief="flat",
        )

        def on_click(event):
            index = self._device_listbox.nearest(event.y)
            bbox = self._device_listbox.bbox(index)
            if bbox is None or event.y > bbox[1] + bbox[3]:
                return "break"

        self._device_listbox.bind("<Button-1>", on_click)

        self._device_listbox.grid(
            row=1, column=0, columnspan=3, sticky="nsew", pady=(6, 6)
        )
        scan_btn = ThemedButton(device_panel, text="Scan", command=self.scan_devices)
        scan_btn.grid(row=2, column=0, sticky="w")
        self._connect_btn = ThemedButton(
            device_panel, text="Connect", command=self.connect
        )
        self._connect_btn.grid(row=2, column=1, sticky="e", padx=(0, 6))
        self._disconnect_btn = ThemedButton(
            device_panel, text="Disconnect", command=self.disconnect
        )
        self._disconnect_btn.grid(row=2, column=2, sticky="e")

        self._find = FindPopup(
            raw_frame,
            self._raw_text,
            self.ui.theme,
            grid_opts={
                "row": 1,
                "column": 0,
                "sticky": "ne",
                "padx": 6,
                "pady": (10, 0),
            },
        )

        bar = tk.Frame(root)
        bar.grid(row=3, column=0, sticky="w", pady=(8, 0))
        root.rowconfigure(3, weight=0)

        self._range_button = ttk.Button(
            bar,
            text="Range",
            style="MenuBar.TButton",
            command=self._show_range_menu,
            padding=6,
            width=0
        )
        self._range_button.pack(side=tk.LEFT, padx=(0, 6))

        for label, cmd in MOMENTARY_COMMANDS:
            btn = ttk.Button(bar, text=label, style="MenuBar.TButton",
                command=lambda c=cmd: self._send_command_prefix(c), padding=6, width=0)
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._mode_buttons.append(btn)

        for label in ("AUTO", "HOLD"):
            var = self._toggle_vars[label]
            btn = ttk.Checkbutton(bar, text=label, style="MenuBar.TCheckbutton",
                variable=var, command=lambda key=label: self._on_toggle_clicked(key))
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._mode_buttons.append(btn)

        def add_cycle_group(kind: str, key: str, options: tuple) -> None:
            var = tk.StringVar(value=options[0][0])
            sel_var = tk.BooleanVar(value=False)
            self._cycle_groups[key] = {"kind": kind, "options": options,
                "label_var": var, "select_var": sel_var}
            btn = ttk.Checkbutton(bar, textvariable=var, style="MenuBar.TCheckbutton",
                variable=sel_var, command=lambda k=key: self._cycle_mode(k))
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._mode_buttons.append(btn)

        for key, options in RANGE_CYCLE_GROUPS:
            add_cycle_group("range", key, options)

        var = self._toggle_vars["CAP"]
        btn = ttk.Checkbutton(bar, text="CAP", style="MenuBar.TCheckbutton",
            variable=var, command=lambda: self._on_toggle_clicked("CAP"))
        btn.pack(side=tk.LEFT, padx=(0, 6))
        self._mode_buttons.append(btn)

        for key, options in COMMAND_CYCLE_GROUPS:
            add_cycle_group("command", key, options)

        self._set_control_state(False)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_theme(self, theme: ThemePalette) -> None:
        self.ui.use_theme(theme)
        theme_title_bar(self, border_color=theme.outline, caption_color=theme.bg)

        self._wave_view.set_colors(self.ui.theme)
        self._find.set_tag_colors(self.ui.theme)

    def _set_control_state(self, enabled: bool) -> None:
        state = "!disabled" if enabled else "disabled"
        for btn in self._mode_buttons:
            btn.state([state])
        if self._range_button is not None:
            self._range_button.state([state])

        if not enabled and self._range_menu is not None:
            self._range_menu.destroy()
            self._range_menu = None

    def _apply_meter_state(self) -> None:
        m = self._last_measurement
        if not m:
            for var in self._toggle_vars.values():
                var.set(False)
            for group in self._cycle_groups.values():
                group["select_var"].set(False)
            return

        status = self._last_device_status
        self._toggle_vars["AUTO"].set((m.range or "").startswith("AUTO"))
        self._toggle_vars["HOLD"].set(status[3])
        self._toggle_vars["CAP"].set(m.kind == "CAP")

        for group in self._cycle_groups.values():
            group["select_var"].set(False)

        kind = m.kind
        if kind in RANGE_KIND_TO_GROUP:
            self._select_cycle_group(RANGE_KIND_TO_GROUP[kind], kind)

        if kind in COMMAND_KIND_TO_GROUP:
            label = COMMAND_KIND_LABELS[kind] if kind in COMMAND_KIND_LABELS else kind
            self._select_cycle_group(COMMAND_KIND_TO_GROUP[kind], label)

    def _select_cycle_group(self, key: str, label: str) -> None:
        group = self._cycle_groups[key]
        if not any(label == option[0] for option in group["options"]):
            return
        group["label_var"].set(label)
        group["select_var"].set(True)

    def _send_command_prefix(self, cmd_prefix: bytes) -> None:
        if not self._worker or not self._worker.alive:
            show_error(
                self,
                "Command",
                "Connect to a device before sending commands.",
                theme=(self.ui.theme.bg, self.ui.theme.outline),
            )
            return
        payload = _build_command_packet(cmd_prefix)
        self._worker.set_command(payload)

    def _cycle_mode(self, key: str) -> None:
        group = self._cycle_groups[key]
        options = group["options"]
        selected_now = group["select_var"].get()
        current_label = group["label_var"].get()
        current_index = 0
        for idx, (label, _) in enumerate(options):
            if label == current_label:
                current_index = idx
                break
        if not selected_now:
            current_index = (current_index + 1) % len(options)
        value = options[current_index][1]
        if isinstance(value, bytes):
            self._send_command_prefix(value)
        elif group["kind"] == "range" and isinstance(value, int):
            self._send_range_flag(value)

        self._apply_meter_state()

    def _on_toggle_clicked(self, key: str) -> None:
        is_on = self._toggle_vars[key].get()
        cmd_on, cmd_off = _TOGGLE_COMMANDS_MAP[key]

        if key == "CAP":
            self._toggle_vars[key].set(True)
            if cmd_on:
                self._send_command_prefix(cmd_on)
        elif is_on and cmd_on:
            self._send_command_prefix(cmd_on)
        elif not is_on:
            if cmd_off:
                self._send_command_prefix(cmd_off)
            elif self._last_base_mode_flag is not None:
                self._send_range_flag(self._last_base_mode_flag)

        self._apply_meter_state()

    def _send_range_flag(self, flag: int) -> None:
        self._last_base_mode_flag = flag
        cmd_prefix = b"\xaf\x05\x03\x06\x01%c" % flag
        self._send_command_prefix(cmd_prefix)

    def _get_active_range_kind(self) -> str | None:
        if self._last_measurement:
            return self._last_measurement.kind
        flag = self._last_base_mode_flag
        if flag is not None and flag in FLAG_INFO:
            return FLAG_INFO[flag][0]

    def _build_range_items(self, kind: str | None) -> list:
        if not kind or kind not in _RANGE_ITEMS_BY_KIND:
            return [("No ranges", None)]

        return [
            (rng, lambda f=flag: self._send_range_flag(f))
            for rng, flag in _RANGE_ITEMS_BY_KIND[kind]
        ]

    def _show_range_menu(self) -> None:
        if self._range_menu is not None:
            self._range_menu.destroy()
            self._range_menu = None
            return

        if self._range_button is None:
            return
        btn = self._range_button
        active_kind = self._get_active_range_kind()
        root = self.winfo_toplevel()
        self._range_menu = MenuDropdown(
            root,
            self._build_range_items(active_kind),
            on_destroy=lambda: setattr(self, '_range_menu', None),
            owner_widget=btn,
            direction=MENU_UP,
        )

    def _ensure_radio_available(self, title: str) -> bool:
        if NanoScanner.radio_state() != "off":
            return True

        message = "Bluetooth radio is OFF. Turn Bluetooth on and try again."
        self._status_var.set(message)
        show_error(
            self,
            title,
            message,
            theme=(self.ui.theme.bg, self.ui.theme.outline),
        )
        return False

    def connect(self) -> None:
        if self._scan_in_progress:
            self._scan_generation += 1
            self._scan_in_progress = False
            cancel_scan, self._scan_cancel = self._scan_cancel, None
            if cancel_scan is not None:
                try:
                    cancel_scan()
                except Exception:
                    pass
        if not self._ensure_radio_available("Connect"):
            return

        selection = self._device_listbox.curselection()
        device = self._devices[selection[0]] if selection else None
        if device is None:
            show_error(
                self,
                "Connect",
                "Select a device from the list.",
                theme=(self.ui.theme.bg, self.ui.theme.outline),
            )
            return
        if self._worker:
            if self._worker.alive:
                return
            self._worker = None

        self._last_trace_key = None
        self._wave_view.clear()
        label = device.name or device.address
        self._status_var.set(f"Connecting to {label} …")

        def _ui(method):
            def _dispatch(*a):
                self.after(0, method, *a)
            return _dispatch

        self._worker = BleWorker(
            device,
            on_packet=_ui(self._on_worker_packet),
            on_tx=_ui(self._on_worker_tx),
            on_status=_ui(self._on_worker_status),
            on_error=_ui(self._on_worker_error),
            on_connected=_ui(self._on_worker_connected),
            on_disconnected=_ui(self._on_worker_disconnected),
        )

    def scan_devices(self) -> None:
        if self._scan_in_progress:
            return
        if not self._ensure_radio_available("Scan"):
            return
        self._scan_generation += 1
        scan_id = self._scan_generation
        self._scan_in_progress = True
        self._scan_cancel = None
        self._devices = []
        self._device_index_by_address.clear()
        self._device_listbox.delete(0, tk.END)
        self._status_var.set("Scanning for devices …")
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
            self.after(0, self._scan_failed, scan_id, exc)
            return
        self.after(0, self._scan_complete, scan_id, devices)

    def _scan_add_device(self, scan_id: int, device) -> None:
        if scan_id != self._scan_generation:
            return
        addr = device.address
        if not addr:
            return
        name = device.name or "Unknown"

        existing_index = self._device_index_by_address.get(addr)
        if existing_index is not None:
            existing_device = self._devices[existing_index]
            existing_device.name = device.name

            current_label = self._device_listbox.get(existing_index)
            desired_label = f"{name} ({addr})"
            # Refresh row when new packets provide a better name for an existing address.
            if name != "Unknown" and current_label != desired_label:
                self._device_listbox.delete(existing_index)
                self._device_listbox.insert(existing_index, desired_label)
            return

        self._device_index_by_address[addr] = len(self._devices)
        self._devices.append(device)
        self._device_listbox.insert(tk.END, f"{name} ({addr})")

    def _scan_failed(self, scan_id: int, exc: Exception) -> None:
        if scan_id != self._scan_generation:
            return
        self._scan_in_progress = False
        self._scan_cancel = None
        self._status_var.set("Scan failed")
        show_error(
            self,
            "Scan",
            f"BLE scan failed: {exc!r}",
            theme=(self.ui.theme.bg, self.ui.theme.outline),
        )

    def _scan_complete(self, scan_id: int, devices: list) -> None:
        if scan_id != self._scan_generation:
            return
        self._scan_in_progress = False
        self._scan_cancel = None
        for device in devices:
            self._scan_add_device(scan_id, device)

        count = len(self._devices)
        self._status_var.set(f"Found {count} device{'s' if count != 1 else ''}")

    def disconnect(self) -> None:
        if self._worker:
            self._worker.stop()
        self._worker = None
        self._status_var.set("Disconnected")
        self._is_connected = False
        self._rate_count = 0
        self._set_control_state(False)
        self._refresh_status_bar()

    def _on_close(self) -> None:
        self.disconnect()
        self.destroy()

    def _on_worker_packet(self, payload: bytes) -> None:
        self._apply_packet(payload)
        self._refresh_status_bar()

    def _on_worker_tx(self, payload: bytes) -> None:
        raw = payload.hex(" ").upper()
        self._append_raw_text(f"TX {raw}\n")
        self._refresh_status_bar()

    def _on_worker_status(self, message: str) -> None:
        self._status_var.set(message)
        self._refresh_status_bar()

    def _on_worker_connected(self, _address: str) -> None:
        self._is_connected = True
        self._model_var.set(MODEL.model_name)
        self._rate_count = 0
        self._rate_start = time.monotonic()
        self._set_control_state(True)
        self._refresh_status_bar()

    def _on_worker_disconnected(self, _address: str) -> None:
        self._is_connected = False
        self._rate_count = 0
        self._status_var.set("Disconnected")
        self._worker = None
        self._set_control_state(False)
        self._refresh_status_bar()

    def _on_worker_error(self, message: str) -> None:
        self._status_var.set(message)
        show_error(
            self, "DM40", message, theme=(self.ui.theme.bg, self.ui.theme.outline)
        )
        self._set_control_state(False)
        self._refresh_status_bar()

    def _append_raw_text(self, text: str) -> None:
        self._raw_text.configure(state="normal")
        self._raw_text.insert("end", text)
        self._raw_text.see("end")
        self._raw_text.configure(state="disabled")

    def _apply_packet(self, data: bytes) -> None:
        m = parse_measurement_for_ui(data)

        self._append_raw_text(f"RX {m.raw}  CRC:{'PASS' if m.crc_ok else 'FAIL'}\n")

        if m.kind == "---":
            return

        self._last_device_status = parse_device_status(data)
        self._last_measurement = m
        self._apply_meter_state()

        trace_key = data[5]
        if self._last_trace_key is not None and trace_key != self._last_trace_key:
            self._wave_view.clear()
            self._stats_count = 0
        self._last_trace_key = trace_key

        self._mode_var.set(f"{m.kind} {m.range}" if m.range else m.kind)
        unit = f" {m.display_unit}" if m.display_unit else ""
        self._value_label.configure(text=f" {m.value_str}{unit}")

        aux = [
            f"{val} {u}".strip()
            for val, u in ((m.sec_val, m.sec_unit), (m.third_val, m.third_unit))
            if val
        ]
        self._aux_var.set("    ".join(aux))
        mul = UNIT_TO_BASE.get(m.display_unit, 1.0)

        if not m.overload and m.norm_value is not None:
            self._wave_view.push(
                m.norm_value,
                pad=m.vertical_pad,
                axis_unit=m.display_unit,
                axis_mul=mul,
                decimals=m.decimals,
            )
            v = m.norm_value
            if self._stats_count == 0:
                self._stats_min = self._stats_max = self._stats_sum = v
            else:
                if v < self._stats_min:
                    self._stats_min = v
                if v > self._stats_max:
                    self._stats_max = v
                self._stats_sum += v
            self._stats_count += 1
            avg = self._stats_sum / self._stats_count
            d = m.decimals
            self._stats_var.set(
                "Min %.*f  Max %.*f  Avg %.*f%s"
                % (d, self._stats_min / mul, d, self._stats_max / mul, d, avg / mul, unit)
            )

        if self._is_connected:
            self._rate_count += 1

    def _refresh_status_bar(self) -> None:
        now = time.monotonic()
        elapsed = int(now - self._start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        run_s = "RUN %02d:%02d:%02d" % (h, m, s)
        self._runtime_var.set(run_s)

        status = self._last_device_status
        self._icons_var.set(("⚡" if status[1] else "") + ("🔒" if status[2] else "") + ("✋" if status[3] else ""))

        charging = status[1]
        target_fg = "#00ff00" if charging else self.option_get("foreground", ".")
        if self._battery_label.cget("foreground") != target_fg:
            self._battery_label.configure(foreground=target_fg)

        segments = max(0, min(5, int(status[0])))
        self._battery_label.configure(text="█" * segments + "░" * (5 - segments))
        if self._is_connected:
            dt = now - self._rate_start
            title_rate = self._rate_count / dt if dt > 0 else 0.0
            if dt >= 2.0:
                self._rate_count = 0
                self._rate_start = now
            title = f"{self._title_base} - {title_rate:.1f} samples/s"
        else:
            title = self._title_base
        if self._wave_view.paused:
            title += "  \u23F8 PAUSED"
        if self._wave_view.recording:
            title += "  \u23FA REC"
        self.title(title)