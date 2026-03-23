"""EL15 DC Electronic Load Tkinter application."""
import tkinter as tk
from tkinter import ttk

from shared.base_app import BaseDeviceApp
from shared.ble_worker import BleWorker
from GUI.themed_messagebox import show_error

from .protocol_constants import (
    EL15Status,
    HEADER,
    POLL_PKT,
    CMD_LOAD_OFF,
    CMD_LOAD_ON,
    CMD_MODE_CC,
    CMD_MODE_CV,
    CMD_MODE_CR,
    CMD_MODE_CP,
    MODE_CC, MODE_CV, MODE_CR, MODE_CP,
    MODE_SETPOINT_INFO,
    build_set_setpoint_cmd,
    parse_status_packet,
)


_MODE_CYCLE = (
    ("CC", MODE_CC,  CMD_MODE_CC),
    ("CV", MODE_CV,  CMD_MODE_CV),
    ("CR", MODE_CR,  CMD_MODE_CR),
    ("CP", MODE_CP,  CMD_MODE_CP),
)


def _el15_notify_filter(data: bytes) -> bool:
    return data[:4] == HEADER


class EL15App(BaseDeviceApp):
    _title_base = "EL15"
    _csv_prefix = "EL15"

    def _init_device_state(self) -> None:
        self._last_status: EL15Status | None = None
        self._mode_buttons: dict[int, ttk.Checkbutton] = {}
        self._mode_vars: dict[int, tk.BooleanVar] = {}
        self._load_var = tk.BooleanVar(value=False)
        self._active_mode = MODE_CC

    def _create_worker(self, device, **callbacks):
        return BleWorker(
            device,
            poll_cmd=POLL_PKT,
            notify_hook=_el15_notify_filter,
            write_buf_size=10,
            **callbacks,
        )

    def _build_menubar_labels(self, menubar) -> None:
        tk.Label(menubar, text="EL15", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=3, sticky="e"
        )
        self._mode_label_var = tk.StringVar(value="")
        tk.Label(menubar, textvariable=self._mode_label_var).grid(
            row=0, column=5, sticky="e", padx=(0, 8)
        )

    def _build_reading_area(self, parent: tk.Frame) -> None:
        readings = tk.Frame(parent)
        readings.pack(fill=tk.X)
        readings.columnconfigure(0, weight=1)
        readings.columnconfigure(1, weight=1)
        readings.columnconfigure(2, weight=1)

        def _make_cell(col: int, header: str) -> ttk.Label:
            cell = tk.Frame(readings)
            cell.grid(row=0, column=col, sticky="ew", padx=(0, 12 if col < 2 else 0))
            tk.Label(cell, text=header, font=("Segoe UI", 11)).pack(anchor="w")
            val_lbl = ttk.Label(
                cell, text="---", font=("Cascadia Mono", 36, "bold"),
                style="DM40.BigValue.TLabel", anchor="e", width=10,
            )
            val_lbl.pack(fill="x")
            return val_lbl

        self._volt_label  = _make_cell(0, "Voltage")
        self._amp_label   = _make_cell(1, "Current")
        self._watt_label  = _make_cell(2, "Power")

        info_bar = tk.Frame(parent)
        info_bar.pack(fill=tk.X, pady=(6, 0))

        self._info_mode_var    = tk.StringVar(value="Mode: ---")
        self._info_load_var    = tk.StringVar(value="Load: OFF")
        self._info_setp_var    = tk.StringVar(value="Setpoint: ---")
        self._info_runtime_var = tk.StringVar(value="Runtime: --:--:--")
        self._info_temp_var    = tk.StringVar(value="Temp: ---")
        self._info_fan_var     = tk.StringVar(value="Fan: -")

        for col, var in enumerate((
            self._info_mode_var, self._info_load_var, self._info_setp_var,
            self._info_runtime_var, self._info_temp_var, self._info_fan_var,
        )):
            tk.Label(info_bar, textvariable=var, font=("Consolas", 10)).grid(
                row=0, column=col, sticky="w", padx=(0, 18)
            )

    def _build_control_bar(self, bar: tk.Frame) -> None:
        for label, mode_val, cmd in _MODE_CYCLE:
            var = tk.BooleanVar(value=False)
            self._mode_vars[mode_val] = var
            btn = ttk.Checkbutton(
                bar, text=label, style="MenuBar.TCheckbutton",
                variable=var,
                command=lambda m=mode_val, c=cmd: self._on_mode_clicked(m, c),
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._mode_buttons[mode_val] = btn

        self._load_btn = ttk.Checkbutton(
            bar, text="Load", style="MenuBar.TCheckbutton",
            variable=self._load_var, command=self._on_load_clicked,
        )
        self._load_btn.pack(side=tk.LEFT, padx=(0, 18))

        tk.Label(bar, text="Setpoint:").pack(side=tk.LEFT, padx=(0, 4))
        self._setpoint_var = tk.StringVar(value="")
        self._setpoint_entry = ttk.Entry(bar, textvariable=self._setpoint_var, width=10)
        self._setpoint_entry.pack(side=tk.LEFT, padx=(0, 4))
        self._setpoint_entry.bind("<Return>", self._on_set_setpoint)
        self._setpoint_unit_var = tk.StringVar(value="A")
        tk.Label(bar, textvariable=self._setpoint_unit_var, width=2).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(bar, text="Set", style="MenuBar.TButton",
                   command=self._on_set_setpoint, padding=6, width=0).pack(side=tk.LEFT)

        self._all_controls: list = [
            *self._mode_buttons.values(),
            self._load_btn,
            self._setpoint_entry,
        ]
        self._set_control_state(False)

    def _set_control_state(self, enabled: bool) -> None:
        state = "!disabled" if enabled else "disabled"
        for widget in self._all_controls:
            widget.state([state])

    def _on_mode_clicked(self, mode_val: int, cmd_prefix: bytes) -> None:
        for m, var in self._mode_vars.items():
            var.set(m == mode_val)
        self._active_mode = mode_val
        info = MODE_SETPOINT_INFO.get(mode_val, ("A", 3, "Current"))
        self._setpoint_unit_var.set(info[0])
        self._send_command_prefix(cmd_prefix)

    def _on_load_clicked(self) -> None:
        self._send_command_prefix(CMD_LOAD_ON if self._load_var.get() else CMD_LOAD_OFF)

    def _on_set_setpoint(self, _event=None) -> None:
        try:
            value = float(self._setpoint_var.get().strip())
        except ValueError:
            show_error(self, "Setpoint", "Enter a valid numeric value.",
                       theme=(self.ui.theme.bg, self.ui.theme.outline))
            return
        self._send_command_prefix(build_set_setpoint_cmd(value))

    def _apply_status_buttons(self, s: EL15Status) -> None:
        for mode_val, var in self._mode_vars.items():
            var.set(s.mode == mode_val)
        self._active_mode = s.mode
        self._load_var.set(s.load_on)
        info = MODE_SETPOINT_INFO.get(s.mode, ("A", 3, "Current"))
        self._setpoint_unit_var.set(info[0])

    def _on_packet_data(self, data: bytes) -> None:
        s = parse_status_packet(data)
        self._append_raw_text(f"RX {s.raw}  CRC:{'PASS' if s.crc_ok else 'FAIL'}\n")

        if not s.valid:
            return

        self._last_status = s
        self._apply_status_buttons(s)

        self._volt_label.configure(text=f"{s.voltage:8.3f} V")
        self._amp_label.configure(text=f"{s.current:8.3f} A")
        self._watt_label.configure(text=f"{s.power:8.3f} W")

        self._info_mode_var.set(f"Mode: {s.mode_name}")
        self._info_load_var.set(f"Load: {'ON' if s.load_on else 'OFF'}")
        self._info_setp_var.set(
            f"{s.setpoint_label}: {s.setpoint:.{s.setpoint_decimals}f} {s.setpoint_unit}"
        )
        rs = s.runtime
        self._info_runtime_var.set(
            "Runtime: %02d:%02d:%02d" % (rs // 3600, (rs % 3600) // 60, rs % 60)
        )
        self._info_temp_var.set(f"Temp: {s.temperature:.1f}°C")
        self._info_fan_var.set(f"Fan: {s.fan_speed}")
        self._mode_label_var.set(f"{s.mode_name}  {'▶ ON' if s.load_on else '◼ OFF'}")

        self._wave_view.push(s.voltage, pad=0.5, axis_unit="V", axis_mul=1.0, decimals=3)

        smin, smax, avg = self._push_stats(s.voltage)
        self._stats_var.set("V  Min %.3f  Max %.3f  Avg %.3f" % (smin, smax, avg))

        if self._is_connected:
            self._rate_count += 1
