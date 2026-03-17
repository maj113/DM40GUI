import tkinter as tk
from tkinter import ttk

MENU_DOWN = 0
MENU_UP = 1


class MenuDropdown(tk.Frame):
    def __init__(
        self,
        master,
        items,
        on_destroy=None,
        owner_widget=None,
        *,
        direction: int = MENU_DOWN,
    ):
        self.on_destroy_cb = on_destroy
        self._toplevel = master.winfo_toplevel()
        self._outside_bind_id = None
        self._escape_bind_id = None
        self._owner_widget = owner_widget
        self._direction = direction

        super().__init__(master, highlightthickness=2)

        self.bind("<Button-1>", lambda e: "break")
        self._outside_bind_id = self._toplevel.bind(
            "<Button-1>", self._on_root_click, add="+"
        )
        self._escape_bind_id = self._toplevel.bind("<Escape>", self._on_escape, add="+")

        self._build_items(items)
        self.update_idletasks()
        if self._owner_widget is not None:
            self._place_menu(self._owner_widget)

    def _remove_global_handlers(self):
        if self._outside_bind_id:
            try:
                self._toplevel.unbind("<Button-1>", self._outside_bind_id)
            except tk.TclError:
                pass
            self._outside_bind_id = None
        if self._escape_bind_id:
            try:
                self._toplevel.unbind("<Escape>", self._escape_bind_id)
            except tk.TclError:
                pass
            self._escape_bind_id = None

    def _on_escape(self, _event=None):
        self.destroy()

    def _place_menu(self, owner: tk.Widget) -> None:
        root = self._toplevel
        menu_w = self.winfo_reqwidth()
        menu_h = self.winfo_reqheight()

        x = owner.winfo_rootx() - root.winfo_rootx()
        y = owner.winfo_rooty() - root.winfo_rooty() + owner.winfo_height()
        if self._direction == MENU_UP:
            y = owner.winfo_rooty() - root.winfo_rooty() - menu_h

        root_w = root.winfo_width()
        root_h = root.winfo_height()
        if root_w:
            x = max(0, min(x, root_w - menu_w))
        if root_h:
            y = max(0, min(y, root_h - menu_h))

        self.place_configure(x=x, y=y)

    def _on_root_click(self, event):
        target = self._toplevel.winfo_containing(event.x_root, event.y_root)
        if target and (self._is_descendant(target) or self._is_owner(target)):
            return
        self.destroy()

    def _is_descendant(self, widget):
        while widget is not None:
            if widget == self:
                return True
            widget = widget.master
        return False

    def _is_owner(self, widget):
        owner = self._owner_widget
        while widget is not None and owner is not None:
            if widget == owner:
                return True
            widget = widget.master
        return False

    def destroy(self):
        self._remove_global_handlers()
        if self.on_destroy_cb:
            self.on_destroy_cb()
            self.on_destroy_cb = None
        super().destroy()

    def _build_items(self, items):
        for item in items:
            if item == "separator":
                sep = tk.Frame(self, height=1, highlightthickness=1)
                sep.pack(fill="x", padx=4, pady=2)
                sep.bind("<Button-1>", lambda e: "break")
                continue

            if not isinstance(item, (list, tuple)) or len(item) < 2:
                raise TypeError("Menu items must be (label, command) tuples/lists")
            label, command = item[0], item[1]
            if not label:
                continue
            btn = ttk.Button(
                self,
                text=label,
                style="MenuBar.TButton",
                padding=(12, 6),
            )
            btn.pack(fill="x", padx=2, pady=2)

            if command:
                btn.configure(command=lambda cmd=command: self._on_click(cmd))
            else:
                btn.state(["disabled"])

    def _on_click(self, command):
        self.destroy()
        command()
        return "break"


class OwnerDrawnMenuBar(tk.Frame):
    def __init__(
        self,
        master,
        menus,
        theme_manager,
        on_theme=None,
        *,
        menu_direction: int = MENU_DOWN,
        **kwargs,
    ):
        self.menus = menus
        self._theme_manager = theme_manager
        self._on_theme = on_theme
        self._menu_direction = menu_direction
        super().__init__(master, padx=0, pady=0, **kwargs)

        self.active_menu = None
        self._active_menu_owner = None
        self._toplevel = self.winfo_toplevel()
        self._toplevel.bind("<Configure>", self._on_toplevel_configure, add="+")

        self._menu_items = {}
        self._menu_buttons = {}
        for idx, (label, items) in enumerate(self.menus):
            btn = ttk.Button(
                self,
                text=label,
                style="MenuBar.TButton",
                command=lambda key=label: self._show_menu(key),
                width=0,
                padding=(12, 6),
            )
            btn.grid(row=0, column=idx)
            self._menu_items[label] = items
            self._menu_buttons[label] = btn

    def _on_toplevel_configure(self, event):
        if self.active_menu and event.widget == self._toplevel:
            self.active_menu.destroy()

    def _on_menu_destroy(self):
        self.active_menu = None
        self._active_menu_owner = None

    def _show_menu(self, key):
        if self._active_menu_owner == key and self.active_menu:
            self.active_menu.destroy()
            return

        if self.active_menu:
            self.active_menu.destroy()

        if key not in self._menu_items or key not in self._menu_buttons:
            return

        items = self._menu_items[key]
        if key == "Themes" and self._theme_manager and not items:
            items = self._build_theme_items()
        btn = self._menu_buttons[key]

        self.active_menu = MenuDropdown(
            self._toplevel,
            items,
            on_destroy=self._on_menu_destroy,
            owner_widget=btn,
            direction=self._menu_direction,
        )
        self._active_menu_owner = key

    def _build_theme_items(self):
        tm = self._theme_manager
        if not tm:
            return []
        items = []
        active_idx = tm.get_active_theme_index()
        names = tm.list_theme_names()

        for idx, name in enumerate(names):
            label = f"[{name}]" if idx == active_idx else name
            items.append((label, lambda theme_idx=idx: self._apply_theme(theme_idx)))

        items.append("separator")
        items.append(("Theme Browser...", tm.open_dialog))
        return items

    def _apply_theme(self, theme_idx: int):
        tm = self._theme_manager
        if not tm:
            return
        theme, apply = tm.activate_theme_index(theme_idx)
        if theme and apply and self._on_theme:
            self._on_theme(theme)
