import tkinter as tk
from tkinter import ttk


class ThemedButton(ttk.Frame):
    """Minimal ttk button wrapper that supplies a themed border frame."""

    BORDER_STYLE = 'Border.TFrame'

    def __init__(self, master=None, *, text="", command=None,
                 border_thickness: int = 2, padding=(10, 6), **kwargs):
        super().__init__(master, style=self.BORDER_STYLE)
        self.button = ttk.Button(
            self,
            text=text,
            command=command,
            padding=padding,
            **kwargs,
        )
        self.button.pack(
            fill=tk.BOTH,
            expand=True,
            padx=border_thickness,
            pady=border_thickness,
        )

    def style_widgets(self, btn_style: str, border_style: str) -> None:
        self.button.configure(style=btn_style)
        super().configure(style=border_style)
