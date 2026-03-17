class ThemePalette:
    __slots__ = (
        "name",
        "bg",
        "widget",
        "text",
        "accent",
        "accent_hover",
        "accent_pressed",
        "outline",
        "alt_text",
        "hover",
        "button",
    )

    def __init__(
        self,
        name,
        bg,
        widget,
        text,
        accent,
        accent_hover,
        accent_pressed,
        outline,
        alt_text,
        hover,
        button,
    ):
        self.name = name
        self.bg = bg
        self.widget = widget
        self.text = text
        self.accent = accent
        self.accent_hover = accent_hover
        self.accent_pressed = accent_pressed
        self.outline = outline
        self.alt_text = alt_text
        self.hover = hover
        self.button = button


class NanoBLEDevice:
    __slots__ = ("address", "name", "rssi", "bluetooth_address")

    def __init__(self, address, name=None, rssi=None, bluetooth_address=0):
        self.address = address
        self.name = name
        self.rssi = rssi
        self.bluetooth_address = bluetooth_address
