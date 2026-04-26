class UIControls:
    def __init__(self, master, style, theme):
        self.master = master
        self.style = style
        self.theme = theme
        style.theme_use("clam")

        self._init_layouts()
        self.apply_theme()

    def use_theme(self, theme) -> None:
        self.theme = theme
        self.apply_theme()

    def apply_theme(self) -> None:
        colors = self.theme
        if not self.master.winfo_exists():
            return
        self.master.tk_setPalette(
            background=colors.bg,
            foreground=colors.text,
            activeBackground=colors.accent,
            activeForeground=colors.text,
            highlightColor=colors.outline,
            highlightBackground=colors.outline,
            selectColor=colors.accent,
            insertBackground=colors.text,
            selectBackground=colors.accent,
            selectForeground=colors.text,
        )

        self._setup_style_colors()

    def _init_layouts(self) -> None:
        style = self.style
        _flat_btn = [("Button.padding", {"sticky": "nswe",
                      "children": [("Button.label", {"sticky": "nswe"})]})]

        style.configure("Border.TFrame", relief="solid")
        style.layout("TFrame", [("Frame.padding", {})])
        style.layout("Border.TFrame", [("Frame.border", {"sticky": "nswe"})])
        style.layout("TLabel", [("Label.label", {"sticky": "nswe"})])
        style.layout("DM40.BigValue.TLabel", [("Label.label", {"sticky": "nswe"})])

        style.configure("TButton", relief="flat")
        style.layout("TButton", _flat_btn)
        style.configure("MenuBar.TCheckbutton", relief="flat")
        style.layout("MenuBar.TCheckbutton",
                     [("Checkbutton.padding", {"sticky": "nswe",
                       "children": [("Checkbutton.label", {"sticky": "nswe"})]})])
        style.configure("FindPopup.TButton", padding=(6, 1))

        style.configure("Arrowless.Vertical.TScrollbar", gripcount=0)
        style.layout("Arrowless.Vertical.TScrollbar",  # type: ignore
                     [("Vertical.Scrollbar.trough",
                       {"children": [("Vertical.Scrollbar.thumb",
                                      {"expand": 1, "sticky": "ns"})],
                        "sticky": "ns"})])

    def _setup_style_colors(self) -> None:
        style = self.style
        colors = self.theme
        edge = colors.outline

        button_base = colors.button
        hover_bg = colors.accent_hover
        pressed_bg = colors.accent_pressed

        def _style_button(name: str, bg: str, hover=hover_bg, pressed=pressed_bg):
            style.configure(name, background=bg, foreground=colors.text)
            style.map(name,
                background=[
                    ("pressed", pressed),
                    ("active", hover),
                ],
                foreground=[("pressed", colors.text), ("active", colors.text)]
            )

        style.configure("Border.TFrame", background=colors.bg, foreground=colors.text,
                       bordercolor=edge, lightcolor=edge, darkcolor=edge)
        _style_button("TButton", button_base)
        _style_button("MenuBar.TButton", colors.bg)
        _style_button("FindPopup.TButton", button_base, hover=colors.hover)

        style.configure("MenuBar.TCheckbutton", background=colors.bg, foreground=colors.text)
        style.map("MenuBar.TCheckbutton",
            background=[("selected", pressed_bg), ("active", hover_bg)],
            foreground=[("selected", colors.text), ("active", colors.text)]
        )
        style.configure("TFrame", background=colors.bg)
        style.configure("TLabel", background=colors.bg, foreground=colors.text)
        style.configure(
            "DM40.BigValue.TLabel", foreground=colors.alt_text, background=colors.bg
        )

        style.configure("TEntry", fieldbackground=colors.widget, foreground=colors.text,
            background=colors.widget, bordercolor=edge, lightcolor=edge, darkcolor=edge,
            focuscolor=edge, selectbackground=colors.accent, selectforeground=colors.text,
            insertcolor=colors.text, inactiveselectbackground=colors.accent)
        style.map("TEntry",
            fieldbackground=[("readonly", colors.widget)],
            bordercolor=[("focus", edge)], lightcolor=[("focus", edge)],
            selectbackground=[("!disabled", colors.accent)],
            selectforeground=[("!disabled", colors.text)]
        )

        style.configure("Arrowless.Vertical.TScrollbar", troughcolor=colors.bg,
            background=colors.accent_hover, bordercolor=colors.bg,
            lightcolor=colors.bg, darkcolor=colors.bg)
        style.map("Arrowless.Vertical.TScrollbar", background=[
            ("disabled", colors.bg), ("pressed", colors.accent_pressed),
            ("active", colors.accent_hover)])
