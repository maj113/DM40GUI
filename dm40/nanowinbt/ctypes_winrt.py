import ctypes


S_OK = 0

ASYNC_STARTED = 0
ASYNC_COMPLETED = 1
ASYNC_CANCELED = 2


class WinRTError(RuntimeError):
    pass


EventRegistrationToken = ctypes.c_int64

GUID = ctypes.c_ubyte * 16
_PPVOID = ctypes.POINTER(ctypes.c_void_p)
_PGUID = ctypes.POINTER(GUID)
_SZ_VOIDP = ctypes.sizeof(ctypes.c_void_p)
_voidp_at = ctypes.c_void_p.from_address
_byref = ctypes.byref
_addressof = ctypes.addressof
_c_void_p = ctypes.c_void_p
_c_long = ctypes.c_long
_c_ulong = ctypes.c_ulong
_c_int = ctypes.c_int
_c_uint32 = ctypes.c_uint32
_c_uint64 = ctypes.c_uint64
_cast = ctypes.cast
_string_at = ctypes.string_at
_PEVENT_TOKEN = ctypes.POINTER(EventRegistrationToken)
_PINT = ctypes.POINTER(ctypes.c_int)
_PINT16 = ctypes.POINTER(ctypes.c_int16)
_PUINT32 = ctypes.POINTER(ctypes.c_uint32)
_PUINT64 = ctypes.POINTER(ctypes.c_uint64)

def _guid(s: str,
    _r=str.replace, _h=bytearray.fromhex, _f=GUID.from_buffer_copy,
):
    b = _h(_r(s, "-", ""))
    b[0:4] = b[3::-1]
    b[4:6] = b[5:3:-1]
    b[6:8] = b[7:5:-1]
    return _f(b)

IID_IASYNC_INFO = _guid("00000036-0000-0000-C000-000000000046")
IID_IAGILE_OBJECT = _guid("94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90")
IID_IUNKNOWN = _guid("00000000-0000-0000-C000-000000000046")

# Typed async completion handler IIDs from WinRT metadata (System.Runtime.WindowsRuntime).
IID_ASYNC_COMPLETED_HANDLER_BLUETOOTH_LE_DEVICE = _guid(
    "9156B79F-C54A-5277-8F8B-D2CC43C7E004"
)
IID_ASYNC_COMPLETED_HANDLER_GATT_DEVICE_SERVICES_RESULT = _guid(
    "74AB0892-A631-5D6C-B1B4-BD2E1A741A9B"
)
IID_ASYNC_COMPLETED_HANDLER_GATT_CHARACTERISTICS_RESULT = _guid(
    "D6A15475-1E72-5C56-98E8-88F4BC3E0313"
)
IID_ASYNC_COMPLETED_HANDLER_GATT_COMM_STATUS = _guid(
    "2154117A-978D-59DB-99CF-6B690CB3389B"
)

# Interface IIDs gathered from runtime introspection and WinSDK 22621 headers.
IID_BLUETOOTH_LE_ADVERTISEMENT_WATCHER = _guid(
    "A6AC336F-F3D3-4297-8D6C-C81EA6623F40"
)
IID_BLUETOOTH_LE_DEVICE3 = _guid("AEE9E493-44AC-40DC-AF33-B2C13C01CA46")
IID_BLUETOOTH_LE_DEVICE6 = _guid("CA7190EF-0CAE-573C-A1CA-E1FC5BFC39E2")
IID_BLUETOOTH_LE_DEVICE_STATICS = _guid("C8CF1A19-F0B6-4BF0-8689-41303DE2D9F4")
IID_BTLE_PREF_CONN_PARAMS_STATICS = _guid("0E3E8EDC-2751-55AA-A838-8FAEEE818D72")
IID_GATT_DEVICE_SERVICE3 = _guid("B293A950-0C53-437C-A9B3-5C3210C6E569")
IID_IBUFFER_FACTORY = _guid("71AF914D-C10F-484B-BC50-14BC623B3A27")
IID_IBUFFER_BYTE_ACCESS = _guid("905A0FEF-BC53-11DF-8C49-001E4FC686DA")

# Delegate specialization IIDs from Windows.Devices.Bluetooth.Advertisement.h.
IID_TYPED_EVENT_HANDLER_WATCHER_RECEIVED = _guid(
    "90EB4ECA-D465-5EA0-A61C-033C8C5ECEF2"
)
IID_TYPED_EVENT_HANDLER_WATCHER_STOPPED = _guid(
    "9936A4DB-DC99-55C3-9E9B-BF4854BD9EAB"
)
IID_TYPED_EVENT_HANDLER_GATTCHAR_VALUECHANGED = _guid(
    "C1F420F6-6292-5760-A2C9-9DDF98683CFC"
)
IID_TYPED_EVENT_HANDLER_BLUETOOTHLEDEVICE_INSPECTABLE = _guid(
    "A90661E2-372E-5D1E-BBBB-B8A2CE0E7C4D"
)


GATT_WRITE_OPTION_WITHOUT_RESPONSE = 1
GATT_CCCD_NONE = 0
GATT_CCCD_NOTIFY = 1

BLUETOOTH_CONNECTION_STATUS_CONNECTED = 1

_IUNKNOWN_BYTES = bytes(IID_IUNKNOWN)
_IAGILE_BYTES = bytes(IID_IAGILE_OBJECT)


# Reusable WINFUNCTYPE prototypes for COM vtable fields and delegate construction.
_QI_FUNC = ctypes.WINFUNCTYPE(
    _c_long,
    _c_void_p,
    _PGUID,
    _PPVOID,
)
_ADDREF_FUNC = ctypes.WINFUNCTYPE(_c_ulong, _c_void_p)
_RELEASE_FUNC = ctypes.WINFUNCTYPE(_c_ulong, _c_void_p)
_TYPED_INVOKE_FUNC = ctypes.WINFUNCTYPE(
    _c_long,
    _c_void_p,
    _c_void_p,
    _c_void_p,
)
_ASYNC_COMPLETED_INVOKE_FUNC = ctypes.WINFUNCTYPE(
    _c_long,
    _c_void_p,
    _c_void_p,
    _c_int,
)


class ComPtr:
    __slots__ = ('ptr',)

    def __init__(self, ptr):
        self.ptr = ptr

    def query_interface(self, iid, /) -> "ComPtr":
        if not self.ptr:
            raise WinRTError("QueryInterface on null COM pointer")
        out = _c_void_p()
        hr = _vtbl_invoke(
            self.ptr, 0, _c_long,
            _ARG_PGUID_PPVOID,
            _byref(iid), _byref(out),
        )
        _check_hresult(hr, "QueryInterface")
        return ComPtr(out)

    def release(self) -> None:
        if not self.ptr:
            return
        _vtbl_invoke(self.ptr, 2, _c_ulong, ())
        self.ptr.value = None


class HString:
    def __init__(self, value: str):
        self._value = value
        self.handle = _c_void_p()

    def __enter__(self) -> ctypes.c_void_p:
        _windows_create_string(
            self._value,
            len(self._value),
            _byref(self.handle),
        )
        return self.handle

    def __exit__(self, exc_type, exc, tb):
        if self.handle:
            _windows_delete_string(self.handle)


def _vtbl_invoke(this_ptr: ctypes.c_void_p | int, index, restype, argtypes, *args):
    # WINFUNCTYPE returns python int pointer instead of c_void_p
    addr = getattr(this_ptr, 'value', this_ptr)
    return _get_vtbl_fn_type(restype, argtypes)(
        _voidp_at(_voidp_at(addr).value + index * _SZ_VOIDP).value  # type: ignore[operator]
    )(this_ptr, *args)


_combase = ctypes.windll.combase

_windows_create_string = _combase.WindowsCreateString
_windows_create_string.argtypes = [
    ctypes.c_wchar_p,
    ctypes.c_uint,
    _PPVOID,
]
_windows_create_string.restype = _c_long

_windows_delete_string = _combase.WindowsDeleteString
_windows_delete_string.argtypes = [_c_void_p]
_windows_delete_string.restype = _c_long

_windows_get_string_raw_buffer = _combase.WindowsGetStringRawBuffer
_windows_get_string_raw_buffer.argtypes = [
    _c_void_p,
    _PUINT32,
]
_windows_get_string_raw_buffer.restype = ctypes.c_wchar_p

_ro_get_activation_factory = _combase.RoGetActivationFactory
_ro_get_activation_factory.argtypes = [
    _c_void_p,
    _PGUID,
    _PPVOID,
]
_ro_get_activation_factory.restype = _c_long

_ro_activate_instance = _combase.RoActivateInstance
_ro_activate_instance.argtypes = [_c_void_p, _PPVOID]
_ro_activate_instance.restype = _c_long

# Cache function prototypes so _vtbl_invoke does not rebuild WINFUNCTYPE objects.
_VTBL_FN_TYPE_CACHE: dict = {}


def _get_vtbl_fn_type(restype: type, argtypes: tuple[type, ...]):
    key = (restype, argtypes)
    fn_type = _VTBL_FN_TYPE_CACHE.get(key)
    if fn_type is None:
        fn_type = ctypes.WINFUNCTYPE(restype, _c_void_p, *argtypes)
        _VTBL_FN_TYPE_CACHE[key] = fn_type
    return fn_type


# Common argtype tuples for _vtbl_invoke call sites.
_ARG_PGUID_PPVOID = (_PGUID, _PPVOID)
_ARG_OUT_INT = (_PINT,)
_ARG_OUT_INT16 = (_PINT16,)
_ARG_OUT_UINT32 = (_PUINT32,)
_ARG_OUT_UINT64 = (_PUINT64,)
_ARG_OUT_VOIDP = (_PPVOID,)
_ARG_OUT_GUID = (_PGUID,)
_ARG_HANDLER_EVENT_TOKEN = (_c_void_p, _PEVENT_TOKEN)
_ARG_UINT32_OUT_VOIDP = (_c_uint32, _PPVOID)
_ARG_UINT64_OUT_VOIDP = (_c_uint64, _PPVOID)
_ARG_CINT_OUT_VOIDP = (_c_int, _PPVOID)
_ARG_GUID_OUT_VOIDP = (GUID, _PPVOID)
_ARG_VOIDP_OUT_VOIDP = (_c_void_p, _PPVOID)
_ARG_VOIDP_CINT_OUT_VOIDP = (_c_void_p, _c_int, _PPVOID)
_ARG_EVENT_TOKEN = (EventRegistrationToken,)
_ARG_VOIDP = (_c_void_p,)
_ARG_CINT = (_c_int,)
_ARG_UINT32 = (_c_uint32,)


def _check_hresult(hr: int, context: str) -> None:
    if hr < 0:
        raise WinRTError("%s failed with HRESULT 0x%08X" % (context, hr & 0xFFFFFFFF))


def release_ptr(ptr) -> None:
    if not ptr:
        return
    _vtbl_invoke(ptr, 2, _c_ulong, ())


def get_activation_factory(runtime_class: str, iid) -> ComPtr:
    with HString(runtime_class) as class_id:
        out = _c_void_p()
        hr = _ro_get_activation_factory(class_id, _byref(iid), _byref(out))
        _check_hresult(hr, f"RoGetActivationFactory({runtime_class})")
        return ComPtr(out)


def activate_instance(runtime_class: str) -> ComPtr:
    with HString(runtime_class) as class_id:
        out = _c_void_p()
        hr = _ro_activate_instance(class_id, _byref(out))
        _check_hresult(hr, f"RoActivateInstance({runtime_class})")
        return ComPtr(out)


def hstring_to_str(value: ctypes.c_void_p | None) -> str:
    if not value:
        return ""
    length = _c_uint32()
    raw = _windows_get_string_raw_buffer(value, _byref(length))
    return ctypes.wstring_at(raw, length.value) if raw else ""


def _prop_int(ptr, index, argtypes, name):
    out = argtypes[0]._type_()
    hr = _vtbl_invoke(ptr, index, _c_long, argtypes, _byref(out))
    _check_hresult(hr, name)
    return out.value


def _prop_ptr(ptr, index, name):
    out = _c_void_p()
    hr = _vtbl_invoke(ptr, index, _c_long, _ARG_OUT_VOIDP, _byref(out))
    _check_hresult(hr, name)
    return out


def _add_evt(ptr, index, handler_ptr, name):
    token = EventRegistrationToken()
    hr = _vtbl_invoke(ptr, index, _c_long, _ARG_HANDLER_EVENT_TOKEN, handler_ptr, _byref(token))
    _check_hresult(hr, name)
    return token


def _remove_evt(ptr, index, token, name):
    hr = _vtbl_invoke(ptr, index, _c_long, _ARG_EVENT_TOKEN, token)
    _check_hresult(hr, name)


def asyncinfo_get_error_code(p): return _prop_int(p, 8, _ARG_OUT_INT, "AsyncInfo.ErrorCode")  # IAsyncInfo::get_ErrorCode
def asyncop_get_results_ptr(p): return _prop_ptr(p, 8, "AsyncOp.GetResults")  # IAsyncOperation::GetResults [8]


def asyncop_set_completed(p, handler_ptr):  # IAsyncOperation::put_Completed [6]
    hr = _vtbl_invoke(p, 6, _c_long, _ARG_VOIDP, handler_ptr)
    _check_hresult(hr, "AsyncOp.put_Completed")


def watcher_put_scanning_mode(p, mode):  # IBluetoothLEAdvertisementWatcher::put_ScanningMode [12]
    hr = _vtbl_invoke(p, 12, _c_long, _ARG_CINT, _c_int(mode))
    _check_hresult(hr, "Watcher.put_ScanningMode")


def watcher_start(p):  # IBluetoothLEAdvertisementWatcher::Start [17]
    hr = _vtbl_invoke(p, 17, _c_long, ())
    _check_hresult(hr, "Watcher.Start")


def watcher_stop(p):  # IBluetoothLEAdvertisementWatcher::Stop [18]
    hr = _vtbl_invoke(p, 18, _c_long, ())
    _check_hresult(hr, "Watcher.Stop")


def watcher_add_received(ptr, handler_ptr): return _add_evt(ptr, 19, handler_ptr, "Watcher.add_Received")  # [19]
def watcher_remove_received(ptr, token): _remove_evt(ptr, 20, token, "Watcher.remove_Received")  # [20]
def watcher_add_stopped(ptr, handler_ptr): return _add_evt(ptr, 21, handler_ptr, "Watcher.add_Stopped")  # [21]
def watcher_remove_stopped(ptr, token): _remove_evt(ptr, 22, token, "Watcher.remove_Stopped")  # [22]


def received_args_get_rssi(p): return _prop_int(p, 6, _ARG_OUT_INT16, "RecvArgs.RSSI")  # IBluetoothLEAdvertisementReceivedEventArgs::get_RawSignalStrengthInDBm [6]
def received_args_get_address(p): return _prop_int(p, 7, _ARG_OUT_UINT64, "RecvArgs.Address")  # ::get_BluetoothAddress [7]


def received_args_get_local_name(args_ptr: ctypes.c_void_p) -> str | None:  # RecvArgs::get_Advertisement [10]
    adv_ptr = _prop_ptr(args_ptr, 10, "RecvArgs.get_Advertisement")
    if not adv_ptr:
        return None
    raw_name = _c_void_p()
    try:
        hr = _vtbl_invoke(adv_ptr, 8, _c_long, _ARG_OUT_VOIDP, _byref(raw_name))  # IBluetoothLEAdvertisement::get_LocalName [8]
        _check_hresult(hr, "Advertisement.get_LocalName")
        name = hstring_to_str(raw_name)
        return name if name else None
    finally:
        _windows_delete_string(raw_name)
        release_ptr(adv_ptr)


def btle_statics_from_bluetooth_address_async(  # IBluetoothLEDeviceStatics::FromBluetoothAddressAsync [7]
    statics_ptr: ctypes.c_void_p,
    bluetooth_address: int,
) -> ctypes.c_void_p:
    operation = _c_void_p()
    hr = _vtbl_invoke(
        statics_ptr,
        7,
        _c_long,
        _ARG_UINT64_OUT_VOIDP,
        _c_uint64(bluetooth_address),
        _byref(operation),
    )
    _check_hresult(hr, "Statics.FromBluetoothAddressAsync")
    return operation


def btle_device6_request_throughput_params(device_ptr: ctypes.c_void_p) -> None:
    """Request ThroughputOptimized connection parameters (interval 12 = 15ms)."""

    # QI Device6 first — absent on Win10
    d6 = _c_void_p()
    if _vtbl_invoke(device_ptr, 0, _c_long,
            _ARG_PGUID_PPVOID,
            _byref(IID_BLUETOOTH_LE_DEVICE6), _byref(d6)) < 0:
        return
    try:
        statics = get_activation_factory(
            "Windows.Devices.Bluetooth.BluetoothLEPreferredConnectionParameters",
            IID_BTLE_PREF_CONN_PARAMS_STATICS)
        preset = _c_void_p()
        _vtbl_invoke(statics.ptr, 7, _c_long, _ARG_OUT_VOIDP, _byref(preset))
        statics.release()
        req = _c_void_p()
        _vtbl_invoke(d6, 8, _c_long,  # RequestPreferredConnectionParameters [8]
            _ARG_VOIDP_OUT_VOIDP,
            preset, _byref(req))
        if req.value:
            release_ptr(req)
        release_ptr(preset)
    except Exception:
        pass
    finally:
        release_ptr(d6)


def btle_device3_get_gatt_services_for_uuid_async(ptr, service_uuid):  # IBluetoothLEDevice3::GetGattServicesForUuidAsync [10]
    op = _c_void_p()
    hr = _vtbl_invoke(ptr, 10, _c_long, _ARG_GUID_OUT_VOIDP, service_uuid, _byref(op))
    _check_hresult(hr, "BTLEDevice3.GetGattServicesForUuidAsync")
    return op


def btle_device_get_connection_status(p): return _prop_int(p, 9, _ARG_OUT_INT, "BTLEDevice.ConnectionStatus")  # IBluetoothLEDevice::get_ConnectionStatus [9]


def btle_device_add_connection_status_changed(ptr, handler_ptr): return _add_evt(ptr, 16, handler_ptr, "BTLEDevice.add_StatusChanged")  # [16]
def btle_device_remove_connection_status_changed(ptr, token): _remove_evt(ptr, 17, token, "BTLEDevice.remove_StatusChanged")  # [17]


def gatt_services_result_get_status(p): return _prop_int(p, 6, _ARG_OUT_INT, "GattServicesResult.Status")  # IGattDeviceServicesResult::get_Status [6]
def gatt_services_result_get_services(p): return _prop_ptr(p, 8, "GattServicesResult.Services")  # ::get_Services [8]


def gatt_service3_get_characteristics_async(ptr):  # IGattDeviceService3::GetCharacteristicsAsync [11]
    op = _c_void_p()
    hr = _vtbl_invoke(ptr, 11, _c_long, _ARG_OUT_VOIDP, _byref(op))
    _check_hresult(hr, "GattService3.GetCharsAsync")
    return op


def gatt_characteristics_result_get_status(p): return _prop_int(p, 6, _ARG_OUT_INT, "GattCharsResult.Status")  # IGattCharacteristicsResult::get_Status [6]
def gatt_characteristics_result_get_characteristics(p): return _prop_ptr(p, 8, "GattCharsResult.Chars")  # ::get_Characteristics [8]


def vector_view_get_size(p): return _prop_int(p, 7, _ARG_OUT_UINT32, "VectorView.Size")  # IVectorView::get_Size [7]


def vector_view_get_at(ptr, index):  # IVectorView::GetAt [6]
    out = _c_void_p()
    hr = _vtbl_invoke(ptr, 6, _c_long, _ARG_UINT32_OUT_VOIDP, _c_uint32(index), _byref(out))
    _check_hresult(hr, "VectorView.GetAt")
    return out


def gatt_characteristic_get_uuid(ptr):  # IGattCharacteristic::get_Uuid [11]
    out = GUID()  # 16 zero bytes
    hr = _vtbl_invoke(ptr, 11, _c_long, _ARG_OUT_GUID, _byref(out))
    _check_hresult(hr, "GattChar.Uuid")
    return out


def gatt_characteristic_add_value_changed(ptr, handler_ptr): return _add_evt(ptr, 20, handler_ptr, "GattChar.add_ValueChanged")  # IGattCharacteristic::add_ValueChanged [20]
def gatt_characteristic_remove_value_changed(ptr, token): _remove_evt(ptr, 21, token, "GattChar.remove_ValueChanged")  # [21]

def gatt_characteristic_write_value_with_option_async(ptr, buffer_ptr, write_option):  # IGattCharacteristic::WriteValueWithOptionAsync [17]
    op = _c_void_p()
    hr = _vtbl_invoke(ptr, 17, _c_long, _ARG_VOIDP_CINT_OUT_VOIDP,
                      buffer_ptr, _c_int(write_option), _byref(op))
    _check_hresult(hr, "GattChar.WriteValueAsync")
    return op


def gatt_characteristic_write_cccd_async(ptr, cccd_value):  # IGattCharacteristic::WriteClientCharacteristicConfigurationDescriptorAsync [19]
    op = _c_void_p()
    hr = _vtbl_invoke(ptr, 19, _c_long, _ARG_CINT_OUT_VOIDP, _c_int(cccd_value), _byref(op))
    _check_hresult(hr, "GattChar.WriteCCCDAsync")
    return op
def gatt_value_changed_args_get_characteristic_value(p): return _prop_ptr(p, 6, "GattValueChanged.Value")  # IGattValueChangedEventArgs::get_CharacteristicValue [6]


def buffer_factory_create(capacity: int) -> ctypes.c_void_p:  # IBufferFactory::Create [6]
    factory = get_activation_factory("Windows.Storage.Streams.Buffer", IID_IBUFFER_FACTORY)
    try:
        value = _c_void_p()
        hr = _vtbl_invoke(
            factory.ptr,
            6,
            _c_long,
            _ARG_UINT32_OUT_VOIDP,
            _c_uint32(capacity),
            _byref(value),
        )
        _check_hresult(hr, "BufferFactory.Create")
        return value
    finally:
        factory.release()


def buffer_set_length(ptr, length):  # IBuffer::put_Length [8]
    hr = _vtbl_invoke(ptr, 8, _c_long, _ARG_UINT32, _c_uint32(length))
    _check_hresult(hr, "Buffer.put_Length")

def buffer_get_data_ptr(buffer_ptr: ctypes.c_void_p):
    ba = _c_void_p()
    hr = _vtbl_invoke(buffer_ptr, 0, _c_long,
        _ARG_PGUID_PPVOID,
        _byref(IID_IBUFFER_BYTE_ACCESS), _byref(ba))
    _check_hresult(hr, "QI IBufferByteAccess")
    try:
        data = _c_void_p()
        hr = _vtbl_invoke(ba, 3, _c_long,  # IBufferByteAccess::Buffer [3]
            _ARG_OUT_VOIDP,
            _byref(data))
        _check_hresult(hr, "BufferByteAccess.Buffer")
        return data
    finally:
        release_ptr(ba)


def buffer_to_bytes(buffer_ptr: ctypes.c_void_p) -> bytes:
    length = _c_uint32()
    hr = _vtbl_invoke(buffer_ptr, 7, _c_long, _ARG_OUT_UINT32, _byref(length))
    _check_hresult(hr, "Buffer.Length")
    n = length.value
    if n == 0:
        return b""
    data = buffer_get_data_ptr(buffer_ptr)
    return _string_at(data, n)


_VTable4 = ctypes.c_void_p * 4


class _ComDelegate:
    """Shared COM delegate protocol: QI + AddRef + Release."""

    def _query_interface(self, this_ptr: ctypes.c_void_p, riid, ppv) -> int:
        rb = bytes(riid.contents)
        if rb == _IUNKNOWN_BYTES or rb == _IAGILE_BYTES or rb == self._iid_bytes:
            ppv[0] = this_ptr
            self._ref_count += 1
            return S_OK
        ppv[0] = _c_void_p()
        return -2147467262

    def _add_ref(self, this_ptr: ctypes.c_void_p) -> int:
        self._ref_count += 1
        return self._ref_count

    def _release(self, this_ptr: ctypes.c_void_p) -> int:
        self._ref_count -= 1
        return self._ref_count

    def _init_com(self, iid, invoke_fn) -> None:
        self._iid = iid
        self._iid_bytes = bytes(iid)
        self._ref_count = 1
        self._fn_qi = _QI_FUNC(self._query_interface)
        self._fn_add_ref = _ADDREF_FUNC(self._add_ref)
        self._fn_release = _RELEASE_FUNC(self._release)
        self._fn_invoke = invoke_fn
        self._vtable = _VTable4(
            _cast(self._fn_qi, _c_void_p).value,
            _cast(self._fn_add_ref, _c_void_p).value,
            _cast(self._fn_release, _c_void_p).value,
            _cast(self._fn_invoke, _c_void_p).value,
        )
        self._lpVtbl = _c_void_p(_addressof(self._vtable))
        self.ptr = _c_void_p(_addressof(self._lpVtbl))


class TypedEventHandlerDelegate(_ComDelegate):
    def __init__(self, iid, callback):
        self._callback = callback
        self._init_com(iid, _TYPED_INVOKE_FUNC(self._invoke))

    def _invoke(self, this_ptr: ctypes.c_void_p, sender: ctypes.c_void_p, args: ctypes.c_void_p) -> int:
        self._callback(sender, args)
        return S_OK


class AsyncOperationCompletedDelegate(_ComDelegate):
    def __init__(self, iid, callback):
        self._callback = callback
        self._init_com(iid, _ASYNC_COMPLETED_INVOKE_FUNC(self._invoke))

    def _invoke(self, this_ptr: ctypes.c_void_p, async_info: ctypes.c_void_p, status: int) -> int:
        self._callback(async_info, status)
        return S_OK
