"""DM40 device handler."""
import tkinter as tk
from tkinter import ttk

from shared.ble_worker import BleWorker
from GUI.widgets.menubar import MENU_UP, MenuDropdown

from .parsing import MODEL, MODEL_TABLE, Measurement, parse_device_status, parse_measurement_for_ui
from .protocol_constants import (
    CMD_ID,
    CMD_READ,
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

_MODEL_PREFIX = b"\xdf\x05\x03\x08\x14"


def _dm40_notify_filter(data: bytes) -> bool:
    if data[:5] == _MODEL_PREFIX:
        idx = data[9] - 0x41
        if 0 <= idx < len(MODEL_TABLE):
            MODEL.model_name, MODEL.device_counts = MODEL_TABLE[idx]
        return False
    return True


class DM40Handler:
    title = "DM40"
    csv_prefix = "DM40"

    def __init__(self, app) -> None:
        self.app = app
        self._last_trace_key: int | None = None
        self._last_device_status: tuple = (0, False, False, False)
        self._last_measurement: Measurement | None = None
        self._mode_buttons: list[ttk.Button | ttk.Checkbutton] = []
        self._range_button: ttk.Button | None = None
        self._range_menu: MenuDropdown | None = None
        self._toggle_vars: dict[str, tk.BooleanVar] = {
            label: tk.BooleanVar(value=False) for label in ("AUTO", "HOLD", "CAP")
        }
        self._cycle_groups: dict = {}
        self._last_base_mode_flag: int | None = None

    def create_worker(self, device, **callbacks):
        return BleWorker(
            device,
            poll_cmd=CMD_READ,
            init_cmd=CMD_ID,
            notify_hook=_dm40_notify_filter,
            write_buf_size=7,
            **callbacks,
        )

    def build_menubar_labels(self, pre: tk.Frame, post: tk.Frame) -> None:
        self._model_var = tk.StringVar(value=MODEL.model_name)
        tk.Label(
            pre, textvariable=self._model_var, font=("Segoe UI", 11, "bold")
        ).pack(side="left")
        self._runtime_var = tk.StringVar(value="")
        tk.Label(pre, textvariable=self._runtime_var).pack(side="left", padx=(8, 0))
        self._icons_var = tk.StringVar(value="")
        tk.Label(post, textvariable=self._icons_var).pack(side="left")
        self._battery_label = tk.Label(post, text="", font=("Consolas", 10))
        self._battery_label.pack(side="left", padx=(0, 8))

    def build_reading_area(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)

        self._mode_var = tk.StringVar(value="---")
        tk.Label(
            parent, textvariable=self._mode_var, font=("Segoe UI", 12, "bold")
        ).grid(row=0, column=0, sticky="w")

        self._value_label = ttk.Label(
            parent,
            text="---",
            font=("Cascadia Mono", 44, "bold"),
            style="DM40.BigValue.TLabel",
            width=12,
            anchor="e",
        )
        self._value_label.grid(row=1, column=0, sticky="w")

        self._aux1_var = tk.StringVar(value="")
        self._aux2_var = tk.StringVar(value="")
        aux_frame = tk.Frame(parent)
        aux_frame.grid(row=2, column=0, sticky="e")
        tk.Label(
            aux_frame,
            textvariable=self._aux1_var,
            font=("Cascadia Mono", 12, "bold"),
            width=12,
            anchor="e",
        ).pack(side="right", padx=(6, 0))
        tk.Label(
            aux_frame,
            textvariable=self._aux2_var,
            font=("Cascadia Mono", 12, "bold"),
            width=12,
            anchor="e",
        ).pack(side="right")

    def build_control_bar(self, bar: tk.Frame) -> None:
        self._range_button = ttk.Button(
            bar,
            text="Range",
            style="MenuBar.TButton",
            command=self._show_range_menu,
            padding=6,
            width=0,
        )
        self._range_button.pack(side=tk.LEFT, padx=(0, 6))

        for label, cmd in MOMENTARY_COMMANDS:
            btn = ttk.Button(
                bar, text=label, style="MenuBar.TButton",
                command=lambda c=cmd: self.app.send_command(c), padding=6, width=0,
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._mode_buttons.append(btn)

        for label in ("AUTO", "HOLD"):
            var = self._toggle_vars[label]
            btn = ttk.Checkbutton(
                bar, text=label, style="MenuBar.TCheckbutton",
                variable=var, command=lambda key=label: self._on_toggle_clicked(key),
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._mode_buttons.append(btn)

        def add_cycle_group(kind: str, key: str, options: tuple) -> None:
            var = tk.StringVar(value=options[0][0])
            sel_var = tk.BooleanVar(value=False)
            self._cycle_groups[key] = {
                "kind": kind, "options": options,
                "label_var": var, "select_var": sel_var,
            }
            btn = ttk.Checkbutton(
                bar, textvariable=var, style="MenuBar.TCheckbutton",
                variable=sel_var, command=lambda k=key: self._cycle_mode(k),
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._mode_buttons.append(btn)

        for key, options in RANGE_CYCLE_GROUPS:
            add_cycle_group("range", key, options)

        var = self._toggle_vars["CAP"]
        btn = ttk.Checkbutton(
            bar, text="CAP", style="MenuBar.TCheckbutton",
            variable=var, command=lambda: self._on_toggle_clicked("CAP"),
        )
        btn.pack(side=tk.LEFT, padx=(0, 6))
        self._mode_buttons.append(btn)

        for key, options in COMMAND_CYCLE_GROUPS:
            add_cycle_group("command", key, options)

        self.set_control_state(False)

        self.app.bind_all("<Control-c>", self._copy_reading)

    def set_control_state(self, enabled: bool) -> None:
        state = "!disabled" if enabled else "disabled"
        for btn in self._mode_buttons:
            btn.state([state])
        if self._range_button is not None:
            self._range_button.state([state])
        if not enabled and self._range_menu is not None:
            self._range_menu.destroy()
            self._range_menu = None

    def pre_connect_reset(self) -> None:
        self._last_trace_key = None

    clear_capture = pre_connect_reset

    def on_connected(self) -> None:
        self._model_var.set(MODEL.model_name)

    def teardown(self) -> None:
        self.app.unbind_all("<Control-c>")

    def refresh_status(self, now: float) -> None:
        app = self.app
        if app._is_connected:
            elapsed = int(now - app._start_time)
            self._runtime_var.set(
                "RUN %02d:%02d:%02d" % (elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60)
            )
        else:
            self._runtime_var.set("")
        status = self._last_device_status
        self._icons_var.set(
            ("⚡" if status[1] else "") +
            ("🔒" if status[2] else "") +
            ("✋" if status[3] else "")
        )
        charging = status[1]
        target_fg = "#00ff00" if charging else self.app.option_get("foreground", ".")
        if self._battery_label.cget("foreground") != target_fg:
            self._battery_label.configure(foreground=target_fg)
        segments = max(0, min(5, int(status[0])))
        self._battery_label.configure(text="█" * segments + "░" * (5 - segments))

    def on_packet(self, data: bytes) -> None:
        app = self.app
        m = parse_measurement_for_ui(data)
        app._append_raw_text(f"RX {m.raw}  CRC:{m.crc_str}\n")

        if m.kind == "---":
            return

        self._last_device_status = parse_device_status(data)
        self._last_measurement = m
        self._apply_meter_state()

        trace_key = data[5]
        if self._last_trace_key is not None and trace_key != self._last_trace_key:
            app._wave_view.clear()
            app._stats_count = 0
        self._last_trace_key = trace_key

        self._mode_var.set(f"{m.kind} {m.range}" if m.range else m.kind)
        unit = f" {m.display_unit}" if m.display_unit else ""
        self._value_label.configure(text=f" {m.value_str}{unit}")

        third = f"{m.third_val} {m.third_unit}".strip() if m.third_val else ""
        sec = f"{m.sec_val} {m.sec_unit}".strip() if m.sec_val else ""
        self._aux1_var.set(sec)
        self._aux2_var.set(third)

        mul = UNIT_TO_BASE[m.display_unit]
        if not m.overload:
            app._wave_view.push(
                m.norm_value, pad=m.vertical_pad, axis_unit=m.display_unit,
                axis_mul=mul, decimals=m.decimals,
            )
            smin, smax, avg = app._push_stats(m.norm_value)
            d = m.decimals
            app._stats_var.set(
                "Min %.*f  Max %.*f  Avg %.*f%s"
                % (d, smin / mul, d, smax / mul, d, avg / mul, unit)
            )

        if app._is_connected:
            app._rate_count += 1

    def _apply_meter_state(self) -> None:
        m = self._last_measurement
        if not m:
            for var in self._toggle_vars.values():
                var.set(False)
            for group in self._cycle_groups.values():
                group["select_var"].set(False)
            return

        self._toggle_vars["AUTO"].set((m.range or "").startswith("AUTO"))
        self._toggle_vars["HOLD"].set(self._last_device_status[3])
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
            self.app.send_command(value)
        elif group["kind"] == "range" and isinstance(value, int):
            self._send_range_flag(value)
        self._apply_meter_state()

    def _on_toggle_clicked(self, key: str) -> None:
        is_on = self._toggle_vars[key].get()
        cmd_on, cmd_off = _TOGGLE_COMMANDS_MAP[key]
        if key == "CAP":
            self._toggle_vars[key].set(True)
            if cmd_on:
                self.app.send_command(cmd_on)
        elif is_on and cmd_on:
            self.app.send_command(cmd_on)
        elif not is_on:
            if cmd_off:
                self.app.send_command(cmd_off)
            elif self._last_base_mode_flag is not None:
                self._send_range_flag(self._last_base_mode_flag)
        self._apply_meter_state()

    def _send_range_flag(self, flag: int) -> None:
        self._last_base_mode_flag = flag
        self.app.send_command(b"\xaf\x05\x03\x06\x01%c" % flag)

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
        self._range_menu = MenuDropdown(
            self.app,
            self._build_range_items(active_kind),
            on_destroy=lambda: setattr(self, "_range_menu", None),
            owner_widget=btn,
            direction=MENU_UP,
        )

    def _copy_reading(self, _event=None) -> None:
        source = _event.widget if _event is not None else self.app.focus_get()
        if isinstance(source, (tk.Text, tk.Entry, ttk.Entry)):
            return
        m = self._last_measurement
        if not m or m.kind == "---":
            return
        unit = f" {m.display_unit}" if m.display_unit else ""
        self.app.clipboard_clear()
        self.app.clipboard_append(f"{m.value_str}{unit}")
