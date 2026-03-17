import tkinter as tk


class Tooltip:
    """Theme-aware tooltip with hover delay."""

    def __init__(
        self,
        master: tk.Misc,
        font_obj,
    ):
        self.master = master
        self._font = font_obj
        self._tip = None
        self._label = None
        self._current_text = None
        self._last_xy = None
        self._after_id = None
        self._pending = None

    def is_visible(self) -> bool:
        return self._tip is not None

    def _cancel_pending_show(self) -> None:
        if self._after_id:
            try:
                self.master.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self._after_id = None
        self._pending = None

    def update_text(self, text: str) -> bool:
        self._cancel_pending_show()

        if self._current_text == text:
            return True

        if not self._tip or not self._label:
            return False

        try:
            self._label.configure(text=text)
        except tk.TclError:
            pass
        self._current_text = text
        return True

    def show(self, text: str, x: int, y: int, delay_ms: int = 150):
        if self._tip:
            self.update_text(text)
            self.move(x, y)
            return

        pending = (text, x, y)
        if self._after_id:
            if self._pending == pending:
                return
            self._cancel_pending_show()
        self._pending = pending
        self._after_id = self.master.after(delay_ms, self._materialize)

    def _materialize(self):
        self._after_id = None
        if not self._pending:
            return
        text, x, y = self._pending
        self._pending = None
        self._create_tip(text, x, y)

    def _create_tip(self, text: str, x: int, y: int):
        if self._tip:
            return
        self._tip = tk.Toplevel(self.master)
        self._tip.wm_overrideredirect(True)
        self._label = tk.Label(
            self._tip,
            text=text,
            wraplength=520,
            justify="left",
            font=self._font,
            padx=5,
            pady=3,
            highlightthickness=2
        )
        self._label.pack(fill=tk.BOTH, expand=True)
        try:
            self._tip.wm_geometry(f"+{x}+{y}")
        except tk.TclError:
            pass
        self._current_text = text
        self._last_xy = (x, y)

    def move(self, x: int, y: int):
        if self._tip:
            xy = (x, y)
            if self._last_xy == xy:
                return
            try:
                self._tip.wm_geometry(f"+{x}+{y}")
            except tk.TclError:
                pass
            self._last_xy = xy

    def hide(self):
        self._cancel_pending_show()
        if self._tip:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
        self._tip = None
        self._label = None
        self._current_text = None
        self._last_xy = None
