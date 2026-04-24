import ctypes


class NanoRadioStateError(RuntimeError):
    pass


_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_RADIO_FUNCS = None

_FIND_RADIO_PARAMS_PTR = ctypes.byref(ctypes.c_ulong(4))  # sizeof(BLUETOOTH_FIND_RADIO_PARAMS)


def _load_radio_functions():
    global _RADIO_FUNCS
    if _RADIO_FUNCS is not None:
        return _RADIO_FUNCS

    bth = ctypes.WinDLL("bthprops.cpl")

    find_first = bth.BluetoothFindFirstRadio
    find_first.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p)]
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

    radio_handle = ctypes.c_void_p()
    radio_handle_ref = ctypes.byref(radio_handle)

    finder = find_first(_FIND_RADIO_PARAMS_PTR, radio_handle_ref)
    if not finder or finder == _INVALID_HANDLE_VALUE:
        return "off"

    try:
        while True:
            connectable = is_connectable(radio_handle)
            close_handle(radio_handle)

            if connectable:
                return "on"

            if not find_next(finder, radio_handle_ref):
                return "off"
    finally:
        find_close(finder)


def ensure_bluetooth_radio_on(operation: str) -> None:
    if get_bluetooth_radio_state() == "off":
        raise NanoRadioStateError(
            f"Bluetooth radio appears OFF; cannot {operation}. Turn Bluetooth on and retry."
        )