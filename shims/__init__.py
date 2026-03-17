import sys

if "__compiled__" in globals(): # Use .pyc only in Nuitka builds
    from . import ctypes as _ctypes # type: ignore

    def install() -> None:
        sys.modules.update({
            "ctypes": _ctypes,
        })
else:
    def install() -> None:
        pass

