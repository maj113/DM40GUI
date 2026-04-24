import tkinter as tk

try:
    import ctypes
    if not hasattr(ctypes, "windll"):
        raise ImportError("ctypes.windll is not available")
    _USER32 = ctypes.windll.user32
    _DWMAPI = ctypes.windll.dwmapi
    _SHCORE = getattr(ctypes.windll, "shcore", None)
except (ImportError, AttributeError, OSError) as exc:
    raise ImportError("Required Windows APIs are not available") from exc

class intptr_t(ctypes._SimpleCData):
    _type_ = "P"
    _csize_ = ctypes.sizeof(ctypes.c_void_p)

class int32(ctypes._SimpleCData):
    _type_ = "i"
    _csize_ = 4


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
    window.update_idletasks()
    hwnd = int(window.wm_frame(), 16)
    if border_color is not None:
        val = int32(_colorref_from_hex(border_color)) if border_color else int32(0)
        if not _set_window_attribute(hwnd, 34, val):
            return False
    if caption_color is None:
        caption_color = border_color
    if caption_color is not None:
        val = int32(_colorref_from_hex(caption_color)) if caption_color else int32(0)
        if not _set_window_attribute(hwnd, 35, val):
            return False
    return True


def center_on_parent(child, parent, w=None, h=None):
    child.update_idletasks()
    try:
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
    except tk.TclError:
        px = py = 0
        pw = child.winfo_screenwidth()
        ph = child.winfo_screenheight()
    if w is None:
        w = child.winfo_reqwidth()
    if h is None:
        h = child.winfo_reqheight()
    x = px + (pw - w) // 2
    y = py + (ph - h) // 2
    child.geometry("%dx%d+%d+%d" % (w, h, x, y))


def ensure_dpi_awareness():
    if hasattr(_USER32, "SetProcessDpiAwarenessContext"):
        _USER32.SetProcessDpiAwarenessContext(intptr_t(-4))
        return
    if _SHCORE is not None and hasattr(_SHCORE, "SetProcessDpiAwareness"):
        _SHCORE.SetProcessDpiAwareness(2)
    elif hasattr(_USER32, "SetProcessDPIAware"):
        _USER32.SetProcessDPIAware()


__all__ = [
    'center_on_parent',
    'ensure_dpi_awareness',
    'theme_title_bar'
]
