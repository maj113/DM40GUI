import ctypes


class NanoRadioStateError(RuntimeError):
    pass


_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_RADIO_FUNCS = None


def _load_radio_functions():
    global _RADIO_FUNCS
    if _RADIO_FUNCS is not None:
        return _RADIO_FUNCS

    bth = ctypes.WinDLL("bthprops.cpl", use_last_error=True)

    find_first = bth.BluetoothFindFirstRadio
    find_first.argtypes = [
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    find_first.restype = ctypes.c_void_p

    find_next = bth.BluetoothFindNextRadio
    find_next.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    find_next.restype = ctypes.c_long

    find_close = bth.BluetoothFindRadioClose
    find_close.argtypes = [ctypes.c_void_p]
    find_close.restype = ctypes.c_long

    is_connectable = bth.BluetoothIsConnectable
    is_connectable.argtypes = [ctypes.c_void_p]
    is_connectable.restype = ctypes.c_long

    close_handle = ctypes.windll.kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_long

    _RADIO_FUNCS = (find_first, find_next, find_close, is_connectable, close_handle)
    return _RADIO_FUNCS


def get_bluetooth_radio_state() -> str:
    try:
        find_first, find_next, find_close, is_connectable, close_handle = _load_radio_functions()
    except Exception:
        return "unknown"

    params = ctypes.c_ulong(4)  # sizeof(BLUETOOTH_FIND_RADIO_PARAMS) = 4
    radio_handle = ctypes.c_void_p()
    finder = find_first(ctypes.byref(params), ctypes.byref(radio_handle))
    if not finder or finder == _INVALID_HANDLE_VALUE:
        return "off"

    any_connectable = False

    try:
        while True:
            try:
                if is_connectable(radio_handle):
                    any_connectable = True
                    break
            finally:
                if radio_handle:
                    close_handle(radio_handle)
                    radio_handle = ctypes.c_void_p()

            next_handle = ctypes.c_void_p()
            if not find_next(finder, ctypes.byref(next_handle)):
                break
            radio_handle = next_handle
    finally:
        find_close(finder)

    return "on" if any_connectable else "off"


def ensure_bluetooth_radio_on(operation: str) -> None:
    state = get_bluetooth_radio_state()
    if state != "off":
        return
    raise NanoRadioStateError(
        f"Bluetooth radio appears OFF; cannot {operation}. Turn Bluetooth on and retry."
    )
