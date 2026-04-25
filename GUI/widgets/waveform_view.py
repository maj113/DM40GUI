import time
import tkinter as tk
from _collections import deque # type: ignore


class WaveformView(tk.Canvas):
    GRID_FRACS = (0.25, 0.5, 0.75)
    _DRAG_PX = 5
    _TIP_PAD_X = 6
    _TIP_PAD_Y = 4
    _TIP_MARGIN = 12

    def __init__(self, master: tk.Misc, *, colors, capacity: int = 600):
        super().__init__(master, highlightthickness=2, bd=0)
        self._cap = max(16, int(capacity))
        self._buf: deque[float] = deque(maxlen=self._cap)
        self._ts: deque[str] = deque(maxlen=self._cap)
        self._extras: deque[tuple[str, str]] = deque(maxlen=self._cap)
        self._pad = 0.0
        self._lo = 0.0
        self._hi = 1.0
        self._axis_unit = ""
        self._axis_mul = 1.0
        self._decimals = 3
        self._plot_visible = False

        # Cached geometry
        self._cw = 0
        self._ch = 0
        self._x_step = 0.0

        # Interaction state (all coords are canvas-local)
        self._hover_idx: int | None = None
        self._last_x = 0
        self._last_y = 0
        self._hover_visible = False
        self._tip_visible = False
        self._paused = False
        self._pause_queue: list[tuple[float, str, float, str]] = []
        self._tracked_idx: int | None = None
        self._sel_range: tuple[int, int] | None = None
        self._sel_visible = False
        self._anchor_x: int | None = None
        self._dragging = False

        # CSV recording
        self._rec_file = None

        # Canvas items
        self._hover_line = self.create_line(0, 0, 0, 0, state="hidden", width=1, tags=("hover",))
        self._hover_dot = self.create_oval(-4, -4, 4, 4, state="hidden", tags=("hover",))
        self._grid_lines = [self.create_line(0, 0, 0, 0, tags=("grid",)) for _ in self.GRID_FRACS]
        self._trace_line = self.create_line(0, 0, 0, 0, state="hidden", width=2, tags=("plot",))
        self._top_text = self.create_text(6, 6, text="Top", state="hidden", anchor="nw", tags=("plot",))
        self._bot_text = self.create_text(0, 0, text="Bot", state="hidden", anchor="sw", tags=("plot",))
        self._sel_rect = self.create_rectangle(
            0, 0, 0, 0, state="hidden", stipple="gray12", width=1, tags=("sel",)
        )
        self._tip_rect = self.create_rectangle(0, 0, 0, 0, state="hidden", width=2, tags=("tip",))
        self._tip_text = self.create_text(0, 0, text="", state="hidden", anchor="nw", tags=("tip",))

        for seq, cb in (
            ("<Configure>", self._on_configure), ("<Motion>", self._on_motion),
            ("<Leave>", self._on_leave), ("<ButtonPress-1>", self._on_press),
            ("<B1-Motion>", self._on_b1_motion), ("<ButtonRelease-1>", self._on_release),
            ("<ButtonPress-3>", self._dismiss), ("<FocusOut>", self._dismiss),
        ):
            self.bind(seq, cb)
        self.set_colors(colors)

    # Helpers

    def _axis_label(self, value: float) -> str:
        unit = f" {self._axis_unit}" if self._axis_unit else ""
        return f"{value / self._axis_mul:.{self._decimals}f}{unit}"

    def _x_to_idx(self, x: int) -> int:
        return int(round(x / self._x_step)) if self._x_step > 0 else -1

    def _idx_to_x(self, idx: int) -> float:
        return idx * self._x_step

    def _px_to_range(self, x1: int, x2: int) -> tuple[int, int]:
        """Pixel x-coords → sorted, clamped (i_start, i_end)."""
        last = len(self._buf) - 1
        return (
            max(0, min(self._x_to_idx(min(x1, x2)), last)),
            max(0, min(self._x_to_idx(max(x1, x2)), last)),
        )

    # In-canvas tooltip

    def _show_tip(self, text: str, x: int, y: int) -> None:
        """Draw tooltip rect + text at canvas coord (x, y), clamping to bounds."""
        self.itemconfigure(self._tip_text, text=text, state="normal")
        bb = self.bbox(self._tip_text)
        if not bb:
            return
        w = bb[2] - bb[0] + 2 * self._TIP_PAD_X
        h = bb[3] - bb[1] + 2 * self._TIP_PAD_Y
        m = self._TIP_MARGIN
        if x + w > self._cw - m: x = self._cw - w - m
        if y + h > self._ch - m: y = self._ch - h - m
        if x < m: x = m
        if y < m: y = m
        self.coords(self._tip_rect, x, y, x + w, y + h)
        self.coords(self._tip_text, x + self._TIP_PAD_X, y + self._TIP_PAD_Y)
        if not self._tip_visible:
            self.itemconfigure(self._tip_rect, state="normal")
            self._tip_visible = True

    def _hide_tip(self) -> None:
        if not self._tip_visible:
            return
        self.itemconfigure("tip", state="hidden")
        self._tip_visible = False

    # Hover / point display

    def _clear_hover(self) -> None:
        self._hover_idx = None
        self._hide_tip()
        if self._hover_visible:
            self.itemconfigure("hover", state="hidden")
            self._hover_visible = False

    def _show_point(self, idx: int, tip_x: int, tip_y: int) -> None:
        """Position hover line/dot and tooltip for buffer index *idx*."""
        self._hover_idx = idx
        h = self._ch
        x = self._idx_to_x(idx)
        value = self._buf[idx]
        span = self._hi - self._lo
        y = (self._hi - value) / span * (h - 1) if span > 0 else (h - 1) / 2
        self.coords(self._hover_line, x, 0, x, h)
        self.coords(self._hover_dot, x - 4, y - 4, x + 4, y + 4)
        if not self._hover_visible:
            self.itemconfigure("hover", state="normal")
            self._hover_visible = True
        tip_label, extra = self._extras[idx]
        text = tip_label or self._axis_label(value)
        if extra:
            text = f"{text}\n{extra}"
        text = f"{text}\n{self._ts[idx]}"
        self._show_tip(text, tip_x, tip_y)

    # Pause

    def toggle_pause(self) -> bool:
        """Toggle pause. Returns new paused state."""
        self._paused = not self._paused
        if not self._paused:
            self._drain_pause_queue()
        return self._paused

    def _drain_pause_queue(self) -> None:
        queue = self._pause_queue
        if not queue:
            return
        self._pause_queue = []
        self._pad = queue[-1][2]
        overflow = max(0, len(self._buf) + len(queue) - self._cap)
        if overflow:
            self._shift_indices(overflow)
        for value, ts, _, tip_label, extra in queue:
            self._buf.append(value)
            self._ts.append(ts)
            self._extras.append((tip_label, extra))
        self.redraw()

    @property
    def paused(self) -> bool:
        return self._paused

    # Tracking / selection

    def _clear_tracking(self) -> None:
        self._tracked_idx = None
        self._clear_hover()

    def _draw_sel(self, s: int, e: int) -> None:
        """Draw selection rectangle and stats tooltip for indices [s, e]."""
        xl, xr = self._idx_to_x(s), self._idx_to_x(e)
        self.coords(self._sel_rect, xl, 0, xr, self._ch)
        if not self._sel_visible:
            self.itemconfigure(self._sel_rect, state="normal")
            self._sel_visible = True
        snap = [self._buf[i] for i in range(s, e + 1)]
        vmin, vmax = min(snap), max(snap)
        self._show_tip(
            f"Min: {self._axis_label(vmin)}  Max: {self._axis_label(vmax)}  "
            f"\u0394: {self._axis_label(vmax - vmin)}\n"
            f"{self._ts[s]} \u2192 {self._ts[e]}  ({e - s + 1} pts)",
            int(round(xr)) + 12, 12,
        )

    def _clear_selection(self) -> None:
        self._sel_range = None
        if self._sel_visible:
            self.itemconfigure(self._sel_rect, state="hidden")
            self._sel_visible = False
        self._hide_tip()

    # Index shifting on deque overflow

    def _shift_indices(self, n: int = 1) -> None:
        if self._tracked_idx is not None:
            self._tracked_idx -= n
            if self._tracked_idx < 0:
                self._clear_tracking()
        if self._sel_range is not None:
            s, e = self._sel_range
            if e < n:
                self._clear_selection()
            else:
                self._sel_range = (max(0, s - n), e - n)

    # Event handlers

    def _on_configure(self, _e=None) -> None:
        w = self.winfo_width() or 1
        h = self.winfo_height() or 1
        if self._cw == w and self._ch == h:
            return
        self._cw = w
        self._ch = h
        self._x_step = (w - 1) / max(1, self._cap - 1)
        h1 = h - 1
        for item, frac in zip(self._grid_lines, self.GRID_FRACS):
            self.coords(item, 0, h1 * frac, w, h1 * frac)
        self.coords(self._bot_text, 6, h - 6)
        self.redraw()

    def _on_leave(self, _e=None) -> None:
        if self._tracked_idx is None and self._sel_range is None:
            self._clear_hover()

    def _on_motion(self, event) -> None:
        if not self._buf or self._dragging or self._tracked_idx is not None or self._sel_range is not None:
            return
        idx = self._x_to_idx(event.x)
        if 0 <= idx < len(self._buf):
            self._last_x = event.x
            self._last_y = event.y
            self._show_point(idx, event.x + 12, event.y + 12)
        else:
            self._clear_hover()

    def _on_press(self, event) -> None:
        self.focus_set()
        self._anchor_x = event.x
        self._dragging = False
        self._clear_selection()

    def _on_b1_motion(self, event) -> None:
        if self._anchor_x is None or not self._buf:
            return
        if not self._dragging and abs(event.x - self._anchor_x) >= self._DRAG_PX:
            self._dragging = True
            self._clear_tracking()
        if self._dragging:
            i1, i2 = self._px_to_range(self._anchor_x, event.x)
            if i1 < i2:
                self._draw_sel(i1, i2)

    def _on_release(self, event) -> None:
        anchor = self._anchor_x
        self._anchor_x = None
        if self._dragging:
            self._dragging = False
            if anchor is not None:
                i1, i2 = self._px_to_range(anchor, event.x)
                if i1 < i2:
                    self._sel_range = (i1, i2)
                    self._draw_sel(i1, i2)
                else:
                    self._clear_selection()
            return
        if not self._buf:
            return
        idx = self._x_to_idx(event.x)
        if 0 <= idx < len(self._buf):
            self._tracked_idx = idx
            self._show_point(idx, int(self._idx_to_x(idx)) + 12, 12)
        else:
            self._clear_tracking()

    def _dismiss(self, _e=None) -> None:
        self._clear_tracking()
        self._clear_selection()

    # Theme

    def set_colors(self, colors) -> None:
        fg, trace, grid, bg = colors.text, colors.accent, colors.outline, colors.bg
        self.itemconfigure(self._trace_line, fill=trace)
        self.itemconfigure(self._hover_line, fill=grid)
        self.itemconfigure(self._hover_dot, fill=trace, outline=trace)
        self.itemconfigure(self._top_text, fill=fg)
        self.itemconfigure(self._bot_text, fill=fg)
        self.itemconfigure("grid", fill=grid)
        self.itemconfigure(self._sel_rect, fill=trace, outline=trace)
        self.itemconfigure(self._tip_rect, fill=bg, outline=grid)
        self.itemconfigure(self._tip_text, fill=fg)

    # Data

    def clear(self) -> None:
        self._buf.clear()
        self._ts.clear()
        self._extras.clear()
        self._pause_queue.clear()
        self._clear_tracking()
        self._clear_selection()
        self._set_plot_visible(False)
        self.stop_recording()

    def push(
        self,
        value: float,
        *,
        pad: float = 0.0,
        axis_unit: str | None = None,
        axis_mul: float | None = None,
        decimals: int | None = None,
        tip_value_label: str = "",
        tooltip_extra: str = "",
    ) -> None:
        if axis_unit is not None:
            self._axis_unit = axis_unit
        if axis_mul is not None:
            self._axis_mul = axis_mul or 1.0
        if decimals is not None:
            self._decimals = max(0, min(9, decimals))
        if self._paused:
            self._pause_queue.append((value, time.strftime("%H:%M:%S"), pad, tip_value_label, tooltip_extra))
            return
        self._pad = pad
        if len(self._buf) == self._cap:
            self._shift_indices()
        self._buf.append(value)
        self._ts.append(time.strftime("%H:%M:%S"))
        self._extras.append((tip_value_label, tooltip_extra))
        if self._rec_file is not None:
            self._rec_file.write(f"{self._ts[-1]},{value}\n")
        self.redraw()

    # Redraw

    def _set_plot_visible(self, visible: bool) -> None:
        if self._plot_visible != visible:
            self._plot_visible = visible
            self.itemconfigure("plot", state="normal" if visible else "hidden")

    def redraw(self) -> None:
        h1 = self._ch - 1
        values = self._buf
        if len(values) < 2 or self._cw < 2 or h1 <= 0:
            self._set_plot_visible(False)
            return
        self._set_plot_visible(True)
        lo, hi = min(values) - self._pad, max(values) + self._pad
        if hi <= lo:
            hi = lo + 1.0
        x_step = self._x_step
        y_scale = h1 / (hi - lo)
        y0 = hi * y_scale
        pts = [coord for i, v in enumerate(values) for coord in (i * x_step, y0 - (v * y_scale))]
        self.coords(self._trace_line, *pts)
        if self._lo != lo or self._hi != hi:
            self._lo, self._hi = lo, hi
            self.itemconfigure(self._top_text, text=f"Top: {self._axis_label(hi)}")
            self.itemconfigure(self._bot_text, text=f"Bot: {self._axis_label(lo)}")
        # Refresh pin / hover / selection
        if self._tracked_idx is not None:
            idx = self._tracked_idx
            if 0 <= idx < len(values):
                self._show_point(idx, int(self._idx_to_x(idx)) + 12, 12)
            else:
                self._clear_tracking()
        elif self._hover_idx is not None:
            idx = self._hover_idx
            if idx < len(values):
                self._show_point(idx, self._last_x + 12, self._last_y + 12)
        if self._sel_range is not None:
            s, e = self._sel_range
            if e >= len(values):
                self._clear_selection()
            else:
                self._draw_sel(s, e)

    def save_buffer_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            f.write("Timestamp,Value\n")
            for ts, v in zip(self._ts, self._buf):
                f.write("%s,%s\n" % (ts, v))

    def toggle_recording(self, path: str) -> None:
        self._rec_file = open(path, "w", newline="")
        self._rec_file.write("Timestamp,Value\n")

    def stop_recording(self) -> None:
        if self._rec_file is not None:
            self._rec_file.close()
            self._rec_file = None

    @property
    def recording(self) -> bool:
        return self._rec_file is not None

