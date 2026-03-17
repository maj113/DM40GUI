from tkinter import ttk


class AutoScrollbar(ttk.Scrollbar):
    def __init__(self, master=None, *, auto_hide=True, **kwargs):
        self._auto_hide = auto_hide
        self._grid_kwargs: dict | None = None
        super().__init__(master, **kwargs)

    def grid(self, **kwargs):
        if kwargs:
            self._grid_kwargs = kwargs
        elif self._grid_kwargs is None:
            info = super().grid_info()
            self._grid_kwargs = {
                k: info[k]
                for k in (
                    'row', 'column', 'rowspan', 'columnspan',
                    'sticky', 'padx', 'pady', 'ipadx', 'ipady'
                )
                if k in info
            }
        return super().grid(**kwargs)

    def _show(self):
        if not self.winfo_ismapped():
            if self._grid_kwargs:
                super().grid(**self._grid_kwargs)
            else:
                super().grid()

    def _hide(self):
        if self.winfo_ismapped():
            super().grid_remove()

    def set(self, first, last):
        super().set(first, last)

        if not self._auto_hide:
            return

        lo = float(first)
        hi = float(last)

        if lo <= 0.0 and hi >= 1.0:
            self._hide()
        else:
            self._show()
