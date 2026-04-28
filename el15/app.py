"""EL15 device handler."""
import tkinter as tk
from tkinter import ttk

from shared.ble_worker import BleWorker
from GUI.themed_messagebox import show_clear, show_error

from .protocol_constants import (
    EL15Status,
    HEADER,
    CAP_SETPOINT_HEADER,
    POLL_PKT,
    CMD_MODE_PREFIX,
    CMD_GET_CAP_SETPOINT,
    MODE_NAMES,
    MODE_CC, MODE_CV, MODE_CR, MODE_CP, MODE_CAP, MODE_DCR,
    MODE_ADV, MODE_POWER, MODE_DT, MODE_ADV_SCAN, MODE_POWER_RPT,
    build_control_cmd,
    build_set_setpoint_cmd,
    parse_cap_setpoint_response,
    parse_status_packet,
)

_MODES = (
    ("CC",  MODE_CC),
    ("CV",  MODE_CV),
    ("CR",  MODE_CR),
    ("CP",  MODE_CP),
    ("CAP", MODE_CAP),
    ("DCR", MODE_DCR),
)
_UNREACHABLE = (MODE_ADV, MODE_POWER, MODE_DT, MODE_ADV_SCAN, MODE_POWER_RPT)
_HIDE_TEMP    = (MODE_CAP, MODE_DCR, MODE_ADV, MODE_POWER, MODE_DT, MODE_ADV_SCAN, MODE_POWER_RPT)
_HIDE_RUNTIME = (MODE_DCR, MODE_ADV, MODE_POWER, MODE_DT, MODE_ADV_SCAN, MODE_POWER_RPT)


def _el15_notify_filter(data: bytes) -> bool:
    return data[:4] in (HEADER, CAP_SETPOINT_HEADER)


_FMT6 = ("%.5f", "%.4f", "%.3f", "%.2f", "%.1f")


def _fmt6(v: float) -> str:
    """Format value with a fixed 6-digit width: decimal floats with magnitude."""
    av = v if v >= 0 else -v
    return _FMT6[(av >= 10) + (av >= 100) + (av >= 1000) + (av >= 10000)] % v


class EL15Handler:
    title = "EL15"
    csv_prefix = "EL15"

    def __init__(self, app) -> None:
        self.app = app
        self._last_status: EL15Status | None = None
        self._last_valid_mode: int = MODE_CC
        self._last_alarm_ui = 0
        self._cap_setpoint: float | None = None
        self._cap_setpoint_query_pending = False
        self._mode_var = tk.IntVar(value=MODE_CC)
        self._load_var = tk.BooleanVar(value=False)
        self._lock_var = tk.BooleanVar(value=False)
        self._all_controls: list = []

    def create_worker(self, device, **callbacks):
        return BleWorker(
            device,
            poll_cmd=POLL_PKT,
            notify_hook=_el15_notify_filter,
            write_buf_size=10,
            cmd_requires_notify=True,
            **callbacks,
        )

    def build_menubar_labels(self, pre: tk.Frame, post: tk.Frame) -> None:
        self._mode_label_var = tk.StringVar(value="EL15")
        tk.Label(
            pre, textvariable=self._mode_label_var,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

    def build_reading_area(self, parent: tk.Frame) -> None:
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
        self._info_load_var    = tk.StringVar(value="Load: OFF  Lock: OFF")
        self._info_setp_var    = tk.StringVar(value="Setpoint: ---")
        self._info_runtime_var = tk.StringVar(value="Runtime: --:--:--")
        self._info_temp_var    = tk.StringVar(value="Temp: ---")
        self._info_fan_var     = tk.StringVar(value="Fan: -")
        self._info_warn_var    = tk.StringVar(value="")

        self._info_labels: dict[str, tk.Label] = {}
        for col, (key, var) in enumerate((
            ("mode", self._info_mode_var), ("load", self._info_load_var),
            ("setp", self._info_setp_var), ("runtime", self._info_runtime_var),
            ("temp", self._info_temp_var), ("fan", self._info_fan_var),
            ("warn", self._info_warn_var),
        )):
            lbl = tk.Label(info_bar, textvariable=var, font=("Consolas", 10))
            lbl.grid(row=0, column=col, sticky="w", padx=(0, 18))
            self._info_labels[key] = lbl

    def build_control_bar(self, bar: tk.Frame) -> None:
        self._mode_buttons: list[ttk.Radiobutton] = []
        for label, mode_val in _MODES:
            btn = ttk.Radiobutton(
                bar, text=label, style="MenuBar.TCheckbutton",
                variable=self._mode_var, value=mode_val,
                command=lambda m=mode_val: self._on_mode_clicked(m),
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._mode_buttons.append(btn)
        # Single disabled radio that reflects whichever unreachable mode is
        # active (POW [A] / POW [DT] / ADV).
        self._unreach_mode = MODE_POWER
        self._unreach_btn = ttk.Radiobutton(
            bar, text="---", style="MenuBar.TCheckbutton",
            variable=self._mode_var, value=self._unreach_mode,
        )
        self._unreach_btn.state(["disabled"])
        self._unreach_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._load_btn = ttk.Checkbutton(
            bar, text="Load", style="MenuBar.TCheckbutton",
            variable=self._load_var, command=self._on_load_clicked,
        )
        self._load_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._lock_btn = ttk.Checkbutton(
            bar, text="Lock", style="MenuBar.TCheckbutton",
            variable=self._lock_var, command=self._on_lock_clicked,
        )
        self._lock_btn.pack(side=tk.LEFT, padx=(0, 18))

        tk.Label(bar, text="Setpoint:").pack(side=tk.LEFT, padx=(0, 4))
        self._setpoint_var = tk.StringVar(value="")
        self._setpoint_entry = ttk.Entry(bar, textvariable=self._setpoint_var, width=10)
        self._setpoint_entry.pack(side=tk.LEFT, padx=(0, 4))
        self._setpoint_entry.bind("<Return>", self._on_set_setpoint)
        self._setpoint_unit_var = tk.StringVar(value="A")
        tk.Label(bar, textvariable=self._setpoint_unit_var, width=2).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self._setpoint_btn = ttk.Button(
            bar,
            text="Set",
            style="MenuBar.TButton",
            command=self._on_set_setpoint,
            padding=6,
            width=0,
        )
        self._setpoint_btn.pack(side=tk.LEFT)

        self._all_controls = [
            *self._mode_buttons,
            self._load_btn,
            self._lock_btn,
            self._setpoint_entry,
            self._setpoint_btn,
        ]
        self.set_control_state(False)

    def set_control_state(self, enabled: bool) -> None:
        state = "!disabled" if enabled else "disabled"
        for widget in self._all_controls:
            widget.state([state])

    def pre_connect_reset(self) -> None:
        self._last_status = None
        self._last_alarm_ui = 0
        self._cap_setpoint = None
        self._cap_setpoint_query_pending = False

    def clear_capture(self) -> None: pass
    def on_connected(self) -> None: pass
    def teardown(self) -> None: pass
    def refresh_status(self, now: float) -> None: pass

    def on_packet(self, data: bytes) -> None:
        app = self.app
        s = parse_status_packet(data)
        app._append_raw_text(f"RX {s.raw}  CRC:{s.crc_str}\n")

        cap_setpoint = parse_cap_setpoint_response(data)
        if cap_setpoint is not None:
            self._cap_setpoint = cap_setpoint
            last = self._last_status
            if last is not None and last.mode == MODE_CAP:
                self._apply_status_buttons(last)
            return

        if not s.valid:
            return

        prev_mode = self._last_status.mode if self._last_status else None
        self._last_status = s
        self._apply_status_buttons(s)
        self._handle_alarm(s)

        if s.mode == MODE_CAP:
            if prev_mode != MODE_CAP:
                self._cap_setpoint_query_pending = True
            if self._cap_setpoint_query_pending:
                self._cap_setpoint_query_pending = False
                self.app.send_command(CMD_GET_CAP_SETPOINT)
        else:
            self._cap_setpoint_query_pending = False

        if s.ready:
            if s.mode == MODE_DCR:
                self._amp_label.configure(text=f"{_fmt6(s.dcr_i1)} A")
                self._watt_label.configure(text=f"{s.dcr_mohm:.1f} m\u03a9")
            else:
                self._amp_label.configure(text=f"{_fmt6(s.current)} A")
                self._watt_label.configure(text=f"{_fmt6(s.power)} W")
            self._info_load_var.set(
                f"Load: {'ON' if s.load_on else 'OFF'}  Lock: {'ON' if s.lock_on else 'OFF'}"
            )
            if s.mode == MODE_CAP:
                self._info_setp_var.set(
                    f"Energy: {s.energy_wh:.4f} Wh  Cap: {s.capacity_ah:.4f} Ah"
                )
            elif s.mode == MODE_DCR:
                self._info_setp_var.set(
                    f"I1: {s.dcr_i1:.3f} A  I2: {s.dcr_i2:.3f} A  R: {s.dcr_mohm:.1f} m\u03a9"
                )
            elif s.setpoint_in_packet:
                self._info_setp_var.set(
                    f"{s.setpoint_label}: {s.setpoint:.{s.setpoint_decimals}f} {s.setpoint_unit}"
                )
            rs = s.runtime
            runtime_label = "Timer" if s.timer_switch and s.load_on else "Runtime"
            self._info_runtime_var.set(
                "%s: %02d:%02d:%02d" % (runtime_label, rs // 3600, (rs % 3600) // 60, rs % 60)
            )
            self._mode_label_var.set(f"EL15 [LOAD {'ON' if s.load_on else 'OFF'}]")
        else:
            self._amp_label.configure(text="--- A")
            self._watt_label.configure(text="--- W")
            self._info_load_var.set("Load: ---  Lock: ---")
            self._info_setp_var.set(f"{s.setpoint_label}: ---")
            self._info_runtime_var.set("Runtime: --:--:--")
            if s.warning_code:
                self._mode_label_var.set(f"EL15 [PROT: {s.warning_code}]")
            else:
                self._mode_label_var.set("EL15 [MENU]")

        self._volt_label.configure(text=f"{_fmt6(s.voltage)} V")
        self._info_mode_var.set(f"Mode: {s.mode_name}")
        if not s.warning_code:
            self._info_temp_var.set(f"Temp: {s.temperature:.3f}\u00b0C")
        self._info_fan_var.set(f"Fan: {s.fan_speed}/5")
        if s.warning_code:
            self._info_warn_var.set(f"\u26a0 {s.warning_code}")
        else:
            self._info_warn_var.set("")

        # Hide fields the current mode doesn't report.
        mode = s.mode
        hide_temp    = mode in _HIDE_TEMP
        hide_runtime = mode in _HIDE_RUNTIME
        hide_setp    = mode in _UNREACHABLE
        for key, hide in (
            ("temp", hide_temp), ("runtime", hide_runtime), ("setp", hide_setp),
            ("warn", not s.warning_code),
        ):
            lbl = self._info_labels[key]
            if hide:
                lbl.grid_remove()
            else:
                lbl.grid()

        if s.ready:
            if s.mode == MODE_DCR:
                app._wave_view.push(
                    s.voltage, pad=0.5, axis_unit="V", axis_mul=1.0, decimals=3,
                    tooltip_extra=f"I1: {s.dcr_i1:.3f} A\nI2: {s.dcr_i2:.3f} A\nR: {s.dcr_mohm:.1f} m\u03a9",
                )
            else:
                app._wave_view.push(
                    s.voltage, pad=0.5, axis_unit="V", axis_mul=1.0, decimals=3,
                    tip_value_label=f"U: {_fmt6(s.voltage)} V",
                    tooltip_extra=f"I: {_fmt6(s.current)} A\nP: {_fmt6(s.power)} W",
                )
            smin, smax, avg = app._push_stats(s.voltage)
            app._stats_var.set("V  Min %.3f  Max %.3f  Avg %.3f" % (smin, smax, avg))

        if app._is_connected:
            app._rate_count += 1

    def _apply_status_buttons(self, s: EL15Status) -> None:
        # CAP|fault == CC|fault and DCR|fault == CV|fault at the byte level,
        # so keep the last known good mode and use it for display during faults.
        if not s.warning:
            self._last_valid_mode = s.mode
        display_mode = self._last_valid_mode
        unreachable = display_mode in _UNREACHABLE
        if unreachable:
            if display_mode != self._unreach_mode:
                self._unreach_mode = display_mode
                self._unreach_btn.configure(value=display_mode)
            self._unreach_btn.configure(text=MODE_NAMES[display_mode])
        elif self._unreach_btn.cget("text") != "---":
            self._unreach_btn.configure(text="---")
        self._mode_var.set(display_mode)
        self._load_var.set(s.load_on)
        self._lock_var.set(s.lock_on)
        self._setpoint_unit_var.set(s.setpoint_unit)
        self._setpoint_entry.state(["disabled" if unreachable else "!disabled"])
        if unreachable:
            self._setpoint_var.set("")
            return
        # Keep the setpoint entry synced to the device unless the user is editing
        # it. CAP reports its setpoint through a separate 0x0A readback packet.
        focus = self._setpoint_entry.focus_get()
        if (
            s.mode == MODE_CAP
            and self._cap_setpoint is not None
            and focus is not self._setpoint_entry
            and focus is not self._setpoint_btn
        ):
            self._setpoint_var.set(f"{self._cap_setpoint:.{s.setpoint_decimals}f}")
            return
        if (
            s.ready and s.setpoint_in_packet
            and focus is not self._setpoint_entry
            and focus is not self._setpoint_btn
        ):
            self._setpoint_var.set(f"{s.setpoint:.{s.setpoint_decimals}f}")

    def _handle_alarm(self, s: EL15Status) -> None:
        alarm_ui = s.alarm_ui
        if alarm_ui == 0:
            self._last_alarm_ui = 0
            return
        if alarm_ui == self._last_alarm_ui:
            return
        self._last_alarm_ui = alarm_ui
        if show_clear(
            self.app,
            "EL15 Alarm",
            s.warning,
            theme=(self.app.ui.theme.bg, self.app.ui.theme.outline),
            detail=None,
        ):
            self.app.send_command(
                build_control_cmd(
                    output_on=s.load_on,
                    lock_on=s.lock_on,
                    clear_alarm=True,
                )
            )

    def _on_mode_clicked(self, mode_val: int) -> None:
        # Revert the radio until the device confirms via the next status packet.
        self._mode_var.set(self._last_valid_mode)
        self.app.send_command(CMD_MODE_PREFIX + bytes((mode_val,)))

    def _on_load_clicked(self) -> None:
        last = self._last_status
        desired_on = self._load_var.get()
        lock_on = bool(last and last.lock_on)
        self._load_var.set(bool(last and last.load_on))
        self.app.send_command(build_control_cmd(output_on=desired_on, lock_on=lock_on))

    def _on_lock_clicked(self) -> None:
        last = self._last_status
        desired_on = self._lock_var.get()
        load_on = bool(last and last.load_on)
        self._lock_var.set(bool(last and last.lock_on))
        self.app.send_command(build_control_cmd(output_on=load_on, lock_on=desired_on))

    def _on_set_setpoint(self, _event=None) -> None:
        try:
            value = float(self._setpoint_var.get().strip())
        except ValueError:
            show_error(self.app, "Setpoint", "Enter a valid numeric value.",
                       theme=(self.app.ui.theme.bg, self.app.ui.theme.outline))
            return
        last = self._last_status
        mode = last.mode if last is not None else self._last_valid_mode
        if mode == MODE_CAP:
            self._cap_setpoint_query_pending = True
        self.app.send_command(build_set_setpoint_cmd(value, mode))
