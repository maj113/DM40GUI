"""Minimal ctypes shim - NT-only, project-subset."""

from _ctypes import (
    _Pointer, _SimpleCData,
    CFuncPtr as _CFuncPtr,
    FUNCFLAG_CDECL as _FUNCFLAG_CDECL,
    FUNCFLAG_STDCALL as _FUNCFLAG_STDCALL,
    FUNCFLAG_PYTHONAPI as _FUNCFLAG_PYTHONAPI,
    FUNCFLAG_USE_ERRNO as _FUNCFLAG_USE_ERRNO,
    FUNCFLAG_USE_LASTERROR as _FUNCFLAG_USE_LASTERROR,
    LoadLibrary as _LoadLibrary,
    sizeof, byref, addressof,
    _memmove_addr, _string_at_addr, _cast_addr, _wstring_at_addr, # type: ignore
)

class c_long(_SimpleCData):
    _type_ = "l"

class c_ulong(_SimpleCData):
    _type_ = "L"

# Windows LLP64: int == long == 4, longlong == 8 (always)
c_int = c_long
c_uint = c_ulong

class c_ubyte(_SimpleCData):
    _type_ = "B"

class c_void_p(_SimpleCData):
    _type_ = "P"

class c_wchar_p(_SimpleCData):
    _type_ = "Z"

class py_object(_SimpleCData):
    _type_ = "O"

# Windows LLP64 sized types (hardcoded, no sizeof loop needed)
class c_int16(_SimpleCData):
    _type_ = "h"

class c_int64(_SimpleCData):
    _type_ = "q"

c_uint32 = c_ulong

class c_uint64(_SimpleCData):
    _type_ = "Q"
c_size_t = c_uint64 if sizeof(c_void_p) == 8 else c_uint

import sys as _sys

if _sys.version_info < (3, 14):
    from _ctypes import POINTER
else:
    def POINTER(cls):
        try:
            return cls.__pointer_type__
        except AttributeError:
            pass
        return type(f'LP_{cls.__name__}', (_Pointer,), {'_type_': cls})

_win_functype_cache = {}

def WINFUNCTYPE(restype, *argtypes, **kw):
    flags = _FUNCFLAG_STDCALL
    if kw.pop("use_errno", False):
        flags |= _FUNCFLAG_USE_ERRNO
    if kw.pop("use_last_error", False):
        flags |= _FUNCFLAG_USE_LASTERROR
    try:
        return _win_functype_cache[(restype, argtypes, flags)]
    except KeyError:
        pass
    class WinFunctionType(_CFuncPtr):
        _argtypes_ = argtypes
        _restype_ = restype
        _flags_ = flags
    _win_functype_cache[(restype, argtypes, flags)] = WinFunctionType
    return WinFunctionType

def _PYFUNCTYPE(restype, *argtypes):
    class CFunctionType(_CFuncPtr):
        _argtypes_ = argtypes
        _restype_ = restype
        _flags_ = _FUNCFLAG_CDECL | _FUNCFLAG_PYTHONAPI
    return CFunctionType

class LibraryLoader:
    _func_flags_ = _FUNCFLAG_STDCALL
    _func_restype_ = c_int

    def __init__(self, name=None, mode=0, handle=None,
                 use_errno=False, use_last_error=False, winmode=None):
        self._FuncPtr = None
        if name is None:
            return

        flags = self._func_flags_
        if use_errno:
            flags |= _FUNCFLAG_USE_ERRNO
        if use_last_error:
            flags |= _FUNCFLAG_USE_LASTERROR
        restype = self._func_restype_

        class _FuncPtr(_CFuncPtr):
            _flags_ = flags
            _restype_ = restype

        self._FuncPtr = _FuncPtr
        if winmode is None:
            winmode = 0x1000  # LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
        self._name = name
        self._handle = handle if handle is not None else _LoadLibrary(name, winmode)

    def __getattr__(self, name):
        if self._FuncPtr is None:
            if name[0] == '_':
                raise AttributeError(name)
            try:
                dll = type(self)(name)
            except OSError:
                raise AttributeError(name)
            setattr(self, name, dll)
            return dll

        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        func = self._FuncPtr((name, self))  # type: ignore[arg-type]
        func.__name__ = name
        setattr(self, name, func)
        return func


WinDLL = LibraryLoader
windll = LibraryLoader()

class _MemmoveFunc(_CFuncPtr):
    _argtypes_ = (c_void_p, c_void_p, c_size_t)
    _restype_ = c_void_p
    _flags_ = _FUNCFLAG_CDECL


memmove = _MemmoveFunc(_memmove_addr)

_cast = _PYFUNCTYPE(py_object, c_void_p, py_object, py_object)(_cast_addr)
def cast(obj, typ):
    return _cast(obj, obj, typ)

string_at = _PYFUNCTYPE(py_object, c_void_p, c_int)(_string_at_addr)
wstring_at = _PYFUNCTYPE(py_object, c_void_p, c_int)(_wstring_at_addr)
