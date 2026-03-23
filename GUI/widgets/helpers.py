import tkinter as tk

try:
    import ctypes
    if not hasattr(ctypes, "windll"):
        raise ImportError("ctypes.windll is not available")
    _USER32 = ctypes.windll.user32
    _DWMAPI = ctypes.windll.dwmapi
    _SHCORE = getattr(ctypes.windll, "shcore", None)
    _HAS_DPI_CONTEXT = hasattr(_USER32, "SetProcessDpiAwarenessContext")
    _HAS_DPI_AWARENESS = _SHCORE is not None and hasattr(
        _SHCORE, "SetProcessDpiAwareness"
    )
    _HAS_DPI_AWARE = hasattr(_USER32, "SetProcessDPIAware")
except (ImportError, AttributeError, OSError) as exc:
    raise ImportError("Required Windows APIs are not available") from exc

DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35

class intptr_t(ctypes._SimpleCData):
    _type_ = "P"
    _csize_ = ctypes.sizeof(ctypes.c_void_p)

class int32(ctypes._SimpleCData):
    _type_ = "i"
    _csize_ = 4

_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = intptr_t(-4)


def _set_window_attribute(hwnd, attribute, value):
    if not hwnd:
        return False
    try:
        ptr = ctypes.byref(value)
        _DWMAPI.DwmSetWindowAttribute(hwnd, attribute, ptr, value._csize_)
    except (AttributeError, OSError):
        return False
    return True


def _colorref_from_hex(value, _bf=bytes.fromhex, _ifb=int.from_bytes):
    return _ifb(_bf(value[1:]), 'little')


def theme_title_bar(window: tk.Tk | tk.Toplevel, *, border_color: str | None = None,
                    caption_color: str | None = None) -> bool:
    """Apply theme-aligned border/caption colors to the window title bar."""
    window.update_idletasks()
    frame = window.wm_frame()
    hwnd = int(frame, 16)
    if border_color is not None:
        if not set_title_bar_border_color(border_color, hwnd=hwnd):
            return False
    if caption_color is None:
        caption_color = border_color
    if caption_color is not None:
        if not set_title_bar_caption_color(caption_color, hwnd=hwnd):
            return False
    return True


def set_title_bar_border_color(color_hex: str | None, hwnd=None) -> bool:
    if not color_hex:
        return _set_window_attribute(hwnd, DWMWA_BORDER_COLOR, int32(0))
    return _set_window_attribute(hwnd, DWMWA_BORDER_COLOR, int32(_colorref_from_hex(color_hex)))


def set_title_bar_caption_color(color_hex: str | None, hwnd=None) -> bool:
    if not color_hex:
        return _set_window_attribute(hwnd, DWMWA_CAPTION_COLOR, int32(0))
    return _set_window_attribute(hwnd, DWMWA_CAPTION_COLOR, int32(_colorref_from_hex(color_hex)))

def ensure_dpi_awareness():
    if _HAS_DPI_CONTEXT:
        _USER32.SetProcessDpiAwarenessContext(
            _DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
        return
    if _HAS_DPI_AWARENESS and _SHCORE:
        _SHCORE.SetProcessDpiAwareness(2)
    elif _HAS_DPI_AWARE:
        _USER32.SetProcessDPIAware()


__all__ = [
    'ensure_dpi_awareness',
    'theme_title_bar'
]
