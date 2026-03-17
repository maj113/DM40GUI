import tkinter as tk
from tkinter import ttk

from dm40.types import ThemePalette


class FindPopup:
    __slots__ = (
        "_text", "_colors", "_grid_opts", "_query_var", "_matches",
        "_current", "_frame", "entry", "_counter", "_prev_btn",
        "_next_btn", "_close_btn", "_tag_all", "_tag_cur",
    )

    def __init__(
        self,
        parent: tk.Misc,
        text: tk.Text,
        colors: ThemePalette,
        *,
        grid_opts: dict | None = None,
    ):
        self._text = text
        self._colors = colors
        self._grid_opts = grid_opts if grid_opts is not None else {"row": 0, "column": 0, "sticky": "e"}

        self._query_var = tk.StringVar()
        self._matches: list[str] = []
        self._current = -1

        self._frame = tk.Frame(parent)
        inner = self._frame

        self.entry = ttk.Entry(inner, textvariable=self._query_var, width=22)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._counter = tk.Label(inner, text="", padx=0, pady=0)
        self._counter.pack(side=tk.LEFT, padx=(8, 6))

        self._prev_btn = ttk.Button(
            inner, text="▲", width=2, command=self.prev, style="FindPopup.TButton"
        )
        self._prev_btn.pack(side=tk.LEFT, padx=(0, 2))

        self._next_btn = ttk.Button(
            inner, text="▼", width=2, command=self.next, style="FindPopup.TButton"
        )
        self._next_btn.pack(side=tk.LEFT, padx=(0, 2))

        self._close_btn = ttk.Button(
            inner, text="Ｘ", width=2, command=self.hide, style="FindPopup.TButton"
        )  # noqa: RUF001
        self._close_btn.pack(side=tk.LEFT)

        self._tag_all = "__find_all__"
        self._tag_cur = "__find_cur__"

        self._query_var.trace_add("write", lambda *_: self._refresh_matches())

        self.entry.bind("<Escape>", self._on_escape)
        self.entry.bind("<Return>", self._on_return)
        self.entry.bind("<Shift-Return>", self._on_shift_return)
        self.entry.bind("<F3>", self._on_return)
        self.entry.bind("<Shift-F3>", self._on_shift_return)

        self._text.bind("<Control-f>", self._on_ctrl_f)
        self._text.bind("<Control-F>", self._on_ctrl_f)
        self._text.bind("<Escape>", self._on_text_escape)

        self.set_tag_colors(self._colors)
        self.hide(clear=False)

    def set_tag_colors(self, colors: ThemePalette) -> None:
        self._colors = colors
        text_fg = colors.text
        match_bg = colors.outline
        cur_bg = colors.accent
        try:
            self._text.tag_configure(
                self._tag_all, background=match_bg, foreground=text_fg
            )
            self._text.tag_configure(
                self._tag_cur, background=cur_bg, foreground=text_fg
            )
        except tk.TclError:
            pass

    def show(self) -> None:
        if not self._frame.winfo_ismapped():
            self._frame.grid(**self._grid_opts)
        self.entry.focus_set()
        self.entry.selection_range(0, tk.END)

        if not self._query_var.get().strip():
            selected = self._safe_get_selected_text()
            if selected:
                self._query_var.set(selected)

        self._refresh_matches()

    def hide(self, *, clear: bool = True) -> None:
        try:
            self._frame.grid_remove()
        except tk.TclError:
            pass
        if clear:
            self._query_var.set("")
        self._clear_find_tags()
        self._counter.configure(text="")
        self._matches = []
        self._current = -1

    def next(self) -> None:
        if not self._matches:
            return
        self._current = (self._current + 1) % len(self._matches)
        self._apply_current()

    def prev(self) -> None:
        if not self._matches:
            return
        self._current = (self._current - 1) % len(self._matches)
        self._apply_current()

    def _on_ctrl_f(self, _event=None):
        self.show()
        return "break"

    def _on_text_escape(self, _event=None):
        if self._frame.winfo_ismapped():
            self.hide()
            return "break"
        return None

    def _on_escape(self, _event=None):
        self.hide()
        self._text.focus_set()
        return "break"

    def _on_return(self, _event=None):
        self.next()
        return "break"

    def _on_shift_return(self, _event=None):
        self.prev()
        return "break"

    def _safe_get_selected_text(self) -> str:
        try:
            raw = self._text.get("sel.first", "sel.last")
        except tk.TclError:
            return ""
        if "\n" in raw or "\r" in raw:
            return ""
        return raw[:128]

    def _clear_find_tags(self) -> None:
        try:
            self._text.tag_remove(self._tag_all, "1.0", "end")
            self._text.tag_remove(self._tag_cur, "1.0", "end")
        except tk.TclError:
            pass

    def _refresh_matches(self) -> None:
        query = self._query_var.get().strip()
        self._matches = []
        self._current = -1

        if not query:
            self._clear_find_tags()
            self._counter.configure(text="No results")
            return

        nocase = query.lower() == query
        text = self._text
        qlen = len(query)

        self._clear_find_tags()
        start = "1.0"
        while True:
            idx = text.search(query, start, stopindex="end-1c", nocase=nocase)
            if not idx:
                break
            self._matches.append(idx)
            try:
                text.tag_add(self._tag_all, idx, f"{idx}+{qlen}c")
            except tk.TclError:
                pass
            start = f"{idx}+1c"

        if not self._matches:
            self._counter.configure(text="No results")
            return

        insert = text.index("insert")
        chosen = 0
        for i, m in enumerate(self._matches):
            if text.compare(m, ">=", insert):
                chosen = i
                break
        self._current = chosen
        self._apply_current()

    def _apply_current(self) -> None:
        if not self._matches or self._current < 0:
            self._counter.configure(text="0 of 0")
            return

        query = self._query_var.get().strip()
        qlen = len(query)
        if qlen <= 0:
            self._counter.configure(text="")
            return

        idx = self._matches[self._current]
        end = f"{idx}+{qlen}c"

        try:
            self._text.tag_remove(self._tag_cur, "1.0", "end")
            self._text.tag_add(self._tag_cur, idx, end)
            self._text.tag_remove("sel", "1.0", "end")
            self._text.tag_add("sel", idx, end)
            self._text.mark_set("insert", end)
            self._text.see(idx)
        except tk.TclError:
            pass

        self._counter.configure(text=f"{self._current + 1} of {len(self._matches)}")
