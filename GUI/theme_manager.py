import winreg
import tkinter as tk
from tkinter import ttk

from shared.theme_store import deserialize_theme_store_palettes
from GUI.widgets.helpers import theme_title_bar
from GUI.widgets.themed_button import ThemedButton

_PREVIEW_FRAME = "ThemePreview.TFrame"
_PREVIEW_LABEL = "ThemePreview.TLabel"
_PREVIEW_ENTRY = "ThemePreview.TEntry"
_PREVIEW_BUTTON = "ThemePreview.TButton"
_PREVIEW_BORDER = "ThemePreviewBorder.TFrame"
_REG_KEY = r"Software\DM40"
_REG_VAL = "active_theme"

_DEFAULT_STORE = b'\nIskra Dark#292929#333333#ffffff#00ada8#579797#006563#00ada8#ffffff#404040#383838\x0bIskra Light#f0f0f0#ffffff#000000#00ada8#579797#006563#00ada8#000000#e0e0e0#e0e0e0\nDMM Orange#000000#0a0a0a#FF9800#FFAB40#FFC070#E65100#FFB84D#FF9800#131313#111111\x08Bleached#ffffff#f0f0f0#000000#a0a0a0#b0b0b0#888888#cccccc#000000#d0d0d0#e0e0e0\x07Haxor++#000000#0f0e0e#e0e0e0#00ff77#585858#444444#00ff77#00ff77#282828#000000\x07Crimson#5e0515#5e0527#08b0c9#07b581#08c78e#069a6e#08b0c9#08b0c9#325d4b#5e0515\x0bDMM Classic#000000#0a0a0a#ffffff#ff9800#3a3a3a#2d7dff#333333#ff9800#131313#111111\x0cPurple Drank#2e003e#3c0035#7eeb8f#4f005a#570063#43004c#7b1fa2#7eeb8f#3e004c#6a1b9a\tCyberpunk#0d0d0d#1f1f1f#ffd700#1effbc#21ffcf#1ad9a0#08b0c9#ffd700#168664#006d6f\x06Sunset#090736#0b0e1f#e91e63#470024#4e0028#3c001f#e91e63#e91e63#28042d#090736\x06Aurora#090736#0b0e1f#00ff77#750872#81097d#630761#00ff77#00ff77#3f0854#090736\nBleached++#ffffff#ffffff#ffffff#ffffff#ffffff#d9d9d9#ffffff#ffffff#ffffff#ffffff\tBlacked++#000000#0f0e0e#e0e0e0#505050#585858#444444#333333#e0e0e0#282828#000000\x04Lean#2e003e#3a004a#e0e0ff#4f005a#570063#43004c#7b1fa2#e0e0ff#3e004c#6a1b9a\x07DeepRed#5e0515#181818#d92929#5d0101#660101#4f0101#b30000#d92929#5e030b#181818\nNeon Night#000000#1a1a1a#ffffff#ff00ff#ff00ff#d900d9#4a4a4a#ffffff#800080#ff00ff\x07Blacked#0f0e0e#1a1a1a#fcfff7#505050#585858#444444#333333#fcfff7#302f2f#404040'


class ThemeManager:
    __slots__ = (
        "master", "style", "_on_apply", "_themes",
        "_active_theme_idx", "_dialog", "_listbox", "sample_button",
    )

    def __init__(
        self,
        master: tk.Tk | tk.Toplevel,
        style: ttk.Style,
        on_apply=None,
    ):
        self.master = master
        self.style = style
        self._on_apply = on_apply

        self._themes = deserialize_theme_store_palettes(_DEFAULT_STORE)
        self._active_theme_idx = self._read_active_index()

        self._dialog = None
        self._listbox = None
        self.sample_button = None

    def _read_active_index(self) -> int:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
                val, _ = winreg.QueryValueEx(key, _REG_VAL)
                if 0 <= val < len(self._themes):
                    return val
        except OSError:
            pass
        return 0

    def _write_theme_store(self) -> None:
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
                winreg.SetValueEx(key, _REG_VAL, 0, winreg.REG_DWORD, self._active_theme_idx)
        except OSError:
            pass

    def list_theme_names(self) -> list[str]:
        return [theme.name for theme in self._themes]

    def get_active_theme_index(self) -> int:
        return self._active_theme_idx

    def get_active_theme(self):
        return self._themes[self._active_theme_idx]

    def activate_theme_index(self, theme_idx: int):
        if self._listbox:
            curs = self._listbox.curselection()
            sel = curs[0] if curs else None
        else:
            sel = None
        theme, changed = self._activate_by_index(theme_idx)
        if changed:
            self._sync_dialog_after_theme_activation(theme, sel)
        return theme, changed

    def open_dialog(self):
        if self._dialog and self._dialog.winfo_exists():
            self._dialog.lift()
            return

        active_theme = self.get_active_theme()
        self._dialog = tk.Toplevel(self.master)
        self._dialog.withdraw()
        self._dialog.title("Theme Browser")
        self._dialog.transient(self.master)
        self._dialog.resizable(False, False)
        self._dialog.protocol("WM_DELETE_WINDOW", self._close_dialog)
        theme_title_bar(
            self._dialog,
            border_color=active_theme.outline,
            caption_color=active_theme.bg,
        )

        container = tk.Frame(self._dialog, padx=12, pady=12)
        container.grid(row=0, column=0, sticky="nsew")

        tk.Label(container, text="Available themes:", padx=0).grid(
            row=0, column=0, sticky="w"
        )

        list_height = max(4, min(len(self._themes), 12))
        self._listbox = tk.Listbox(
            container,
            height=list_height,
            exportselection=False,
            activestyle="none",
            borderwidth=0,
            highlightthickness=2,
            relief="flat",
            selectborderwidth=0,
            selectmode=tk.BROWSE,
        )
        self._listbox.grid(row=1, column=0, sticky="nsew", pady=(4, 8))
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self._listbox.bind("<<ListboxSelect>>", self._update_preview_from_selection)

        preview = ttk.Frame(container, padding=10, style=_PREVIEW_FRAME)
        preview.grid(row=2, column=0, sticky="nsew")

        sample_label = ttk.Label(preview, text="Sample label", style=_PREVIEW_LABEL)
        sample_label.grid(row=0, column=0, padx=6, pady=6)

        sample_entry = ttk.Entry(preview, style=_PREVIEW_ENTRY)
        sample_entry.insert(0, "Example entry text")
        sample_entry.grid(row=0, column=1, padx=6, pady=6)

        self._init_preview_styles()
        self.sample_button = ThemedButton(
            preview, text="Sample button", padding=(10, 4)
        )
        self.sample_button.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")

        btn_row = tk.Frame(container)
        btn_row.grid(row=3, column=0, pady=(10, 0), sticky="e")

        apply_btn = ThemedButton(
            btn_row, text="Apply", command=self._apply_selected_theme, padding=(10, 4)
        )
        apply_btn.grid(row=0, column=0, padx=(0, 6))
        close_btn = ThemedButton(
            btn_row, text="Close", command=self._close_dialog, padding=(10, 4)
        )
        close_btn.grid(row=0, column=1)

        self._refresh_listbox()
        self._select_listbox_index(self._active_theme_idx)
        self._update_preview_from_selection()
        self._center_dialog()
        self._dialog.deiconify()

    def _close_dialog(self):
        if self._dialog and self._dialog.winfo_exists():
            self._dialog.destroy()
        self._dialog = None
        self._listbox = None
        self.sample_button = None

    def _refresh_listbox(self):
        if not self._listbox:
            return
        self._listbox.delete(0, tk.END)
        for idx, theme in enumerate(self._themes):
            suffix = " (active)" if idx == self._active_theme_idx else ""
            self._listbox.insert(tk.END, f"{theme.name}{suffix}")

    def _update_listbox_active(self, old_idx: int):
        lb = self._listbox
        if not lb:
            return
        new_idx = self._active_theme_idx
        lb.delete(old_idx)
        lb.insert(old_idx, self._themes[old_idx].name)
        lb.delete(new_idx)
        lb.insert(new_idx, f"{self._themes[new_idx].name} (active)")

    def _select_listbox_index(self, idx):
        if not self._listbox:
            return
        size = self._listbox.size()
        if not size:
            return
        idx = max(0, min(idx, size - 1))
        self._listbox.selection_set(idx)
        self._listbox.activate(idx)

    def _sync_dialog_after_theme_activation(self, theme, preserve_index: int | None = None):
        if not self._dialog or not self._dialog.winfo_exists():
            return

        target_idx = self._active_theme_idx
        if preserve_index is not None and 0 <= preserve_index < len(self._themes):
            target_idx = preserve_index

        self._select_listbox_index(target_idx)
        self._apply_dialog_chrome(theme)
        self._update_preview_from_selection()

    def _update_preview_from_selection(self, _event=None):
        if not self._listbox:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._themes):
            return
        theme = self._themes[idx]
        self._apply_preview_colors(theme)
        if self.sample_button:
            try:
                self.sample_button.style_widgets(_PREVIEW_BUTTON, _PREVIEW_BORDER)
            except tk.TclError:
                pass

    def _apply_selected_theme(self):
        if not self._listbox:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        theme, changed = self._activate_by_index(sel[0])
        if not changed or theme is None:
            return
        if self._on_apply:
            self._on_apply(theme)
        self._apply_dialog_chrome(theme)
        self._select_listbox_index(self._active_theme_idx)
        self._update_preview_from_selection()

    def _activate_by_index(self, idx: int):
        if idx < 0 or idx >= len(self._themes):
            return None, False
        if self._active_theme_idx == idx:
            return self._themes[idx], False

        old_idx = self._active_theme_idx
        self._active_theme_idx = idx
        self._write_theme_store()
        self._update_listbox_active(old_idx)
        return self._themes[idx], True

    def _apply_dialog_chrome(self, theme):
        dialog = self._dialog
        if not dialog or not dialog.winfo_exists():
            return

        theme_title_bar(
            dialog,
            border_color=theme.outline,
            caption_color=theme.bg,
        )

    def _init_preview_styles(self):
        self.style.layout(_PREVIEW_BORDER, self.style.layout("Border.TFrame"))
        self.style.configure(_PREVIEW_BORDER, relief="solid")

    def _apply_preview_colors(self, theme):
        self.style.configure(
            _PREVIEW_FRAME,
            background=theme.bg,
        )
        self.style.configure(
            _PREVIEW_LABEL,
            background=theme.bg,
            foreground=theme.text,
        )
        self.style.configure(
            _PREVIEW_ENTRY,
            fieldbackground=theme.widget,
            foreground=theme.text,
            background=theme.widget,
            bordercolor=theme.outline,
            lightcolor=theme.outline,
            darkcolor=theme.outline,
            focuscolor=theme.outline,
            insertcolor=theme.text,
            selectbackground=theme.accent,
            selectforeground=theme.text,
            inactiveselectbackground=theme.accent,
        )
        self.style.map(
            _PREVIEW_ENTRY,
            fieldbackground=[("readonly", theme.widget)],
            bordercolor=[("focus", theme.outline)],
            lightcolor=[("focus", theme.outline)],
            selectbackground=[("!disabled", theme.accent)],
            selectforeground=[("!disabled", theme.text)],
        )
        self.style.configure(
            _PREVIEW_BORDER,
            background=theme.bg,
            foreground=theme.text,
            bordercolor=theme.outline,
            lightcolor=theme.outline,
            darkcolor=theme.outline,
        )
        self.style.configure(
            _PREVIEW_BUTTON,
            background=theme.button,
            foreground=theme.text,
        )
        self.style.map(
            _PREVIEW_BUTTON,
            background=[
                ("pressed", theme.accent_pressed),
                ("active", theme.accent_hover),
            ],
            foreground=[
                ("pressed", theme.text),
                ("active", theme.text),
            ],
        )

    def _center_dialog(self):
        dialog = self._dialog
        master = self.master
        if not dialog or not master:
            return

        dialog.update_idletasks()
        master.update_idletasks()

        if master.winfo_exists():
            x0 = master.winfo_rootx()
            y0 = master.winfo_rooty()
            w0 = master.winfo_width()
            h0 = master.winfo_height()

            w = dialog.winfo_reqwidth()
            h = dialog.winfo_reqheight()

            x = x0 + (w0 - w) // 2
            y = y0 + (h0 - h) // 2

            dialog.geometry(f"{w}x{h}+{x}+{y}")
