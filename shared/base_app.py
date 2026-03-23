"""Shared scaffold for device windows."""
import _thread
import time
import tkinter as tk
from tkinter import ttk

from shared import mini_asyncio as asyncio
from shared.nanowinbt.scanner import NanoScanner

from GUI.controls import UIControls
from GUI.theme_manager import ThemeManager
from GUI.themed_messagebox import show_error
from GUI.widgets.autoscrollbar import AutoScrollbar
from GUI.widgets.find_popup import FindPopup
from GUI.widgets.helpers import theme_title_bar
from GUI.widgets.menubar import OwnerDrawnMenuBar
from GUI.widgets.themed_button import ThemedButton
from GUI.widgets.waveform_view import WaveformView


class BaseDeviceApp(tk.Toplevel):

    _title_base: str = ""
    _csv_prefix: str = ""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)

        self._start_time = time.monotonic()
        self.title(self._title_base)
        self.minsize(916, 650)
        self.wm_geometry("916x650")

        self.style = ttk.Style(self)
        self._theme_manager = ThemeManager(self, self.style, self._apply_theme)
        initial_theme = self._theme_manager.get_active_theme()
        self.ui = UIControls(self, self.style, theme=initial_theme)
        theme_title_bar(self, border_color=initial_theme.outline, caption_color=initial_theme.bg)

        self._worker = None
        self._is_connected = False
        self._devices: list = []
        self._device_index_by_address: dict[str, int] = {}
        self._scan_in_progress = False
        self._scan_generation = 0
        self._scan_cancel = None

        self._reset_stats()

        self._rate_count = 0
        self._rate_start = time.monotonic()

        self._init_device_state()
        self._build_ui()

        self.bind_all("<Key-p>", self._toggle_wave_pause)
        self.bind_all("<Control-s>", self._save_wave_csv)
        self.bind_all("<Key-r>", self._toggle_wave_record)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_device_state(self) -> None: pass

    def _create_worker(self, device, **callbacks):
        raise NotImplementedError

    def _build_menubar_labels(self, menubar) -> None: pass

    def _build_reading_area(self, parent: tk.Frame) -> None:
        raise NotImplementedError

    def _build_control_bar(self, bar: tk.Frame) -> None: pass

    def _set_control_state(self, enabled: bool) -> None:
        raise NotImplementedError

    def _on_packet_data(self, data: bytes) -> None:
        raise NotImplementedError

    def _send_command_prefix(self, cmd_prefix: bytes) -> None:
        if not self._worker or not self._worker.alive:
            show_error(self, "Command", "Connect to a device before sending commands.",
                       theme=(self.ui.theme.bg, self.ui.theme.outline))
            return
        self._worker.set_command(b"%b%c" % (cmd_prefix, (-sum(cmd_prefix)) & 0xFF))

    def _on_connected_extra(self) -> None: pass
    def _pre_connect_reset(self) -> None: pass
    def _clear_capture_extra(self) -> None: pass
    def _refresh_device_status_extra(self, now: float) -> None: pass

    def _reset_stats(self) -> None:
        self._stats_count = 0
        self._stats_sum = self._stats_min = self._stats_max = 0.0

    def _push_stats(self, value: float) -> tuple[float, float, float]:
        if self._stats_count == 0:
            self._stats_min = self._stats_max = self._stats_sum = value
        else:
            if value < self._stats_min:
                self._stats_min = value
            if value > self._stats_max:
                self._stats_max = value
            self._stats_sum += value
        self._stats_count += 1
        return self._stats_min, self._stats_max, self._stats_sum / self._stats_count

    def _build_ui(self) -> None:
        self._menu_bar = OwnerDrawnMenuBar(
            self,
            menus=[
                ("File", [
                    ("Save Buffer", self._save_wave_csv),
                    ("Record", self._toggle_wave_record),
                    "separator",
                    ("Clear", self._clear_capture_data),
                    "separator",
                    ("Exit", self._on_close),
                ]),
                ("Themes", []),
            ],
            theme_manager=self._theme_manager,
            on_theme=self._apply_theme,
        )
        self._menu_bar.pack(fill=tk.X)
        self._menu_bar.grid_columnconfigure(2, weight=1)

        self._runtime_var = tk.StringVar(value="")
        tk.Label(self._menu_bar, textvariable=self._runtime_var).grid(
            row=0, column=4, sticky="w"
        )
        self._build_menubar_labels(self._menu_bar)

        self._status_var = tk.StringVar(value="Disconnected")

        root = tk.Frame(self, padx=12, pady=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)

        mid = tk.Frame(root)
        mid.grid(row=0, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=3)

        reading_host = tk.Frame(mid)
        reading_host.pack(fill=tk.X)
        self._build_reading_area(reading_host)

        self._wave_view = WaveformView(mid, colors=self.ui.theme, capacity=600)
        self._wave_view.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self._stats_var = tk.StringVar(value="")
        tk.Label(mid, textvariable=self._stats_var, font=("Consolas", 10),
                 anchor="w").pack(fill=tk.X, pady=(0, 10))

        raw_frame = tk.Frame(root)
        raw_frame.grid(row=1, column=0, sticky="nsew")
        raw_frame.columnconfigure(0, weight=1)
        raw_frame.rowconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        tk.Label(raw_frame, text="Raw packets:").grid(row=0, column=0, sticky="w")

        self._raw_text = tk.Text(
            raw_frame,
            wrap="none",
            height=10,
            relief="flat",
            highlightthickness=2,
            undo=False,
            maxundo=0,
            autoseparators=False,
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
        tk.Label(device_panel, textvariable=self._status_var).grid(
            row=0, column=1, columnspan=2, sticky="e"
        )

        self._device_listbox = tk.Listbox(
            device_panel,
            height=10,
            width=58,
            exportselection=False,
            activestyle="none",
            highlightthickness=2,
            relief="flat",
        )

        def _on_click(event):
            index = self._device_listbox.nearest(event.y)
            bbox = self._device_listbox.bbox(index)
            if bbox is None or event.y > bbox[1] + bbox[3]:
                return "break"

        self._device_listbox.bind("<Button-1>", _on_click)
        self._device_listbox.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(6, 6))

        scan_btn = ThemedButton(device_panel, text="Scan", command=self.scan_devices)
        scan_btn.grid(row=2, column=0, sticky="w")
        self._connect_btn = ThemedButton(device_panel, text="Connect", command=self.connect)
        self._connect_btn.grid(row=2, column=1, sticky="e", padx=(0, 6))
        self._disconnect_btn = ThemedButton(device_panel, text="Disconnect", command=self.disconnect)
        self._disconnect_btn.grid(row=2, column=2, sticky="e")

        self._find = FindPopup(
            raw_frame,
            self._raw_text,
            self.ui.theme,
            grid_opts={"row": 1, "column": 0, "sticky": "ne", "padx": 6, "pady": (10, 0)},
        )

        bar = tk.Frame(root)
        bar.grid(row=2, column=0, sticky="w", pady=(8, 0))
        root.rowconfigure(2, weight=0)
        self._build_control_bar(bar)

    def _apply_theme(self, theme) -> None:
        self.ui.use_theme(theme)
        theme_title_bar(self, border_color=theme.outline, caption_color=theme.bg)
        self._wave_view.set_colors(self.ui.theme)
        self._find.set_tag_colors(self.ui.theme)

    _CSV_DIR = __compiled__.containing_dir if '__compiled__' in globals() else __file__.rsplit('\\', 2)[0]  # type: ignore[name-defined]

    def _csv_path(self, prefix: str) -> str:
        return f"{self._CSV_DIR}\\{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.csv"

    def _toggle_wave_pause(self, _event=None) -> None:
        self._wave_view.toggle_pause()
        self._refresh_status_bar()

    def _save_wave_csv(self, _event=None) -> None:
        self._wave_view.save_buffer_csv(self._csv_path(self._csv_prefix))

    def _toggle_wave_record(self, _event=None) -> None:
        if self._wave_view.recording:
            self._wave_view.stop_recording()
        else:
            self._wave_view.toggle_recording(self._csv_path(f"{self._csv_prefix}_rec"))
        self._refresh_status_bar()

    def _clear_capture_data(self) -> None:
        self._wave_view.clear()
        self._raw_text.configure(state="normal")
        self._raw_text.delete("1.0", "end")
        self._raw_text.configure(state="disabled")
        self._reset_stats()
        self._stats_var.set("")
        self._clear_capture_extra()
        self._refresh_status_bar()

    def _ensure_radio_available(self, title: str) -> bool:
        if NanoScanner.radio_state() != "off":
            return True
        message = "Bluetooth radio is OFF. Turn Bluetooth on and try again."
        self._status_var.set(message)
        show_error(self, title, message, theme=(self.ui.theme.bg, self.ui.theme.outline))
        return False

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
            self.after(0, self._scan_done, scan_id, [], exc)
            return
        self.after(0, self._scan_done, scan_id, devices or [], None)

    def _scan_add_device(self, scan_id: int, device) -> None:
        if scan_id != self._scan_generation:
            return
        addr = device.address
        if not addr:
            return
        name = device.name or "Unknown"
        existing_index = self._device_index_by_address.get(addr)
        if existing_index is not None:
            self._devices[existing_index].name = device.name
            current_label = self._device_listbox.get(existing_index)
            desired_label = f"{name} ({addr})"
            if name != "Unknown" and current_label != desired_label:
                self._device_listbox.delete(existing_index)
                self._device_listbox.insert(existing_index, desired_label)
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
            show_error(self, "Connect", "Select a device from the list.",
                       theme=(self.ui.theme.bg, self.ui.theme.outline))
            return
        if self._worker:
            if self._worker.alive:
                return
            self._worker = None

        self._pre_connect_reset()
        self._wave_view.clear()
        label = device.name or device.address
        self._status_var.set(f"Connecting to {label} …")

        self._alive = True
        _alive = self.__dict__
        def _ui(method):
            def _dispatch(*a):
                self.after(0, _guarded, method, *a)
            return _dispatch
        def _guarded(method, *a):
            if '_alive' in _alive:
                method(*a)
                self._refresh_status_bar()

        self._worker = self._create_worker(
            device,
            on_packet=_ui(self._on_worker_packet),
            on_tx=_ui(self._on_worker_tx),
            on_status=_ui(self._on_worker_status),
            on_error=_ui(self._on_worker_error),
            on_connected=_ui(self._on_worker_connected),
            on_disconnected=_ui(self._on_worker_disconnected),
        )

    def disconnect(self) -> None:
        self.__dict__.pop('_alive', None)
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
        self._on_packet_data(payload)

    def _on_worker_tx(self, payload: bytes) -> None:
        self._append_raw_text(f"TX {payload.hex(' ').upper()}\n")

    def _on_worker_status(self, message: str) -> None:
        self._status_var.set(message)

    def _on_worker_connected(self, _address: str) -> None:
        self._is_connected = True
        self._rate_count = 0
        self._rate_start = time.monotonic()
        self._set_control_state(True)
        self._on_connected_extra()

    def _on_worker_disconnected(self, _address: str) -> None:
        self._is_connected = False
        self._rate_count = 0
        self._status_var.set("Disconnected")
        self._worker = None
        self._set_control_state(False)

    def _on_worker_error(self, message: str) -> None:
        self._status_var.set(message)
        show_error(self, self._title_base, message,
                   theme=(self.ui.theme.bg, self.ui.theme.outline))
        self._set_control_state(False)

    def _append_raw_text(self, text: str) -> None:
        self._raw_text.configure(state="normal")
        self._raw_text.insert("end", text)
        self._raw_text.see("end")
        self._raw_text.configure(state="disabled")

    def _refresh_status_bar(self) -> None:
        now = time.monotonic()
        elapsed = int(now - self._start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        self._runtime_var.set("RUN %02d:%02d:%02d" % (h, m, s))

        if self._is_connected:
            dt = now - self._rate_start
            rate = self._rate_count / dt if dt > 0 else 0.0
            if dt >= 2.0:
                self._rate_count = 0
                self._rate_start = now
            title = f"{self._title_base} - {rate:.1f} samples/s"
        else:
            title = self._title_base
        if self._wave_view.paused:
            title += "  \u23F8 PAUSED"
        if self._wave_view.recording:
            title += "  \u23FA REC"
        self.title(title)

        self._refresh_device_status_extra(now)
