import tkinter as tk

from GUI.widgets.helpers import theme_title_bar
from GUI.widgets.themed_button import ThemedButton

INFO_ICON = 0
ERROR_ICON = 1

_ICON_LIST = ("i", "✕")


class _ThemedDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        title,
        message,
        *,
        theme,
        icon=ERROR_ICON,
        detail=None,
        buttons=None,
        default=None,
        cancel_value=None,
    ):
        super().__init__(parent)
        self._layout_root = None
        self._target_size = (None, None)
        self.withdraw()
        self.resizable(False, False)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(cancel_value))
        self._result = cancel_value
        bg, outline = theme
        theme_title_bar(self, border_color=outline, caption_color=bg)
        self._build_ui(
            message, icon, detail, buttons or [("OK", True)], default, cancel_value
        )
        self.update_idletasks()
        self._apply_minsize()
        self._center(parent)
        self.deiconify()
        self.wait_window()

    def _build_ui(self, message, icon, detail, buttons, default, cancel_value):
        pad = 12
        container = tk.Frame(self, padx=pad, pady=pad)
        container.pack(fill=tk.BOTH, expand=False)
        self._layout_root = container

        container.grid_columnconfigure(1, weight=1)

        if detail:
            message = f"{message}\n\n{detail}\n" if message else detail
        wrap_length = 260
        icon_text = _ICON_LIST[icon]

        if icon_text:
            icon_label = tk.Label(
                container,
                text=icon_text,
                font=("Segoe UI", 18, "bold"),
            )
            icon_label.grid(row=0, column=0, sticky="n", padx=(0, 12))

        msg_label = tk.Label(
            container,
            text=message,
            justify="left",
            wraplength=wrap_length,
        )
        msg_label.grid(row=0, column=1, sticky="w")

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="e", pady=(6, 0))

        self.bind("<Escape>", lambda _e: self._finish(cancel_value))

        for idx, (text, value) in enumerate(reversed(buttons)):
            btn = ThemedButton(
                btn_frame,
                text=text,
                command=lambda v=value: self._finish(v),
                padding=(8, 4),
                border_thickness=2,
            )
            btn.pack(
                side=tk.RIGHT if idx == 0 else tk.LEFT,
                padx=((8, 0) if idx == 0 else (0, 4)),
            )

            if default == value:
                btn.button.focus_set()
                self.bind("<Return>", lambda _e, v=value: self._finish(v))

    def _apply_minsize(self):
        container = self._layout_root
        if not container:
            return
        try:
            container.update_idletasks()
            required_w = container.winfo_reqwidth()
            required_h = container.winfo_reqheight()
        except tk.TclError:
            return
        min_w = max(required_w, 140)
        min_h = max(required_h, 40)
        try:
            self.minsize(min_w, min_h)
            self.geometry(f"{min_w}x{min_h}")
            self.update_idletasks()
        except tk.TclError:
            return
        self._target_size = (min_w, min_h)

    def _center(self, parent):
        try:
            self.update_idletasks()
        except tk.TclError:
            pass

        try:
            parent.update_idletasks()
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
        except tk.TclError:
            parent_x = parent_y = 0
            parent_w = self.winfo_screenwidth()
            parent_h = self.winfo_screenheight()

        target_w, target_h = self._target_size
        w = target_w if target_w else self.winfo_width()
        h = target_h if target_h else self.winfo_height()
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _finish(self, value):
        self._result = value
        self.grab_release()
        self.destroy()

    @property
    def result(self):
        return self._result


def _show_dialog(
    parent,
    title,
    message,
    *,
    theme: tuple,
    icon,
    buttons,
    default,
    cancel_value,
    detail=None,
):
    parent = parent or getattr(tk, "_default_root", None)
    if parent is None:
        raise RuntimeError("No Tk root window is available")
    dialog = _ThemedDialog(
        parent,
        title,
        message,
        theme=theme,
        icon=icon,
        detail=detail,
        buttons=buttons,
        default=default,
        cancel_value=cancel_value,
    )
    return dialog.result


def show_error(parent, title, message, *, theme: tuple, detail=None):
    return _show_dialog(
        parent,
        title,
        message,
        theme=theme,
        icon=ERROR_ICON,
        buttons=[("OK", True)],
        default=True,
        cancel_value=True,
        detail=detail,
    )



