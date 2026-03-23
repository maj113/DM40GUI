import ctypes


RO_INIT_MULTITHREADED = 1


_combase = ctypes.windll.combase
_ro_initialize = _combase.RoInitialize
_ro_initialize.argtypes = [ctypes.c_ulong]
_ro_initialize.restype = ctypes.c_long

_ro_uninitialize = _combase.RoUninitialize
_ro_uninitialize.argtypes = []
_ro_uninitialize.restype = None


class RoSession:
    __slots__ = ('_state',)

    def __init__(self):
        self._state = 0

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.uninitialize()

    def initialize(self) -> None:
        if self._state:
            return
        hr = _ro_initialize(RO_INIT_MULTITHREADED)
        if hr < 0 and hr != -2147417850:
            raise RuntimeError("RoInitialize failed: 0x%08X" % (hr & 0xFFFFFFFF))
        self._state = 2 if hr in (0, 1) else 1

    def uninitialize(self) -> None:
        if not self._state:
            return
        if self._state == 2:
            _ro_uninitialize()
        self._state = 0
