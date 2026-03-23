from .. import mini_asyncio as asyncio
from ..nanowinbt import ctypes_winrt as w
from .ctypes_com import RoSession
from .radio import ensure_bluetooth_radio_on, get_bluetooth_radio_state
from shared.types import NanoBLEDevice


class NanoScanner:
    @classmethod
    def radio_state(cls) -> str:
        return get_bluetooth_radio_state()

    @classmethod
    async def discover(cls, timeout: float = 5.0, **kwargs) -> list[NanoBLEDevice]:
        return await _discover(timeout, **kwargs)


async def _discover(timeout: float, *, scanning_mode: str = "active", on_device=None, on_cancel_register=None, require_radio_check: bool = True) -> list[NanoBLEDevice]:
    if require_radio_check:
        ensure_bluetooth_radio_on("scan")

    with RoSession():
        inspectable = w.activate_instance(
            "Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementWatcher"
        )
        watcher = inspectable.query_interface(w.IID_BLUETOOTH_LE_ADVERTISEMENT_WATCHER)
        inspectable.release()

        loop = asyncio.get_running_loop()
        dispatch = loop.call_soon_threadsafe
        done = asyncio.Event()

        devices: dict[int, NanoBLEDevice] = {}

        def handle_received(addr: int, rssi: int, name: str | None, device: NanoBLEDevice | None) -> None:
            if device is None:
                device = NanoBLEDevice(address=_format_bdaddr(addr), name=name, rssi=rssi, bluetooth_address=addr)
                devices[addr] = device
            else:
                device.rssi = rssi
                if name and not device.name:
                    device.name = name

            if on_device is not None:
                on_device(device)

        def on_received(_sender, args_ptr) -> None:
            try:
                addr = w.received_args_get_address(args_ptr)
                rssi = w.received_args_get_rssi(args_ptr)
                dev = devices.get(addr)
                name = None if (dev and dev.name) else w.received_args_get_local_name(args_ptr)
            except Exception:
                return
            dispatch(handle_received, addr, rssi, name, dev)

        received_delegate = w.TypedEventHandlerDelegate(w.IID_TYPED_EVENT_HANDLER_WATCHER_RECEIVED, on_received)
        stopped_delegate = w.TypedEventHandlerDelegate(w.IID_TYPED_EVENT_HANDLER_WATCHER_STOPPED, lambda _s, _a: dispatch(done.set))

        timeout_handle = loop.call_later(timeout, done.set)
        if on_cancel_register:
            on_cancel_register(lambda: dispatch(done.set))

        token_rx = token_stop = None
        try:
            w.watcher_put_scanning_mode(watcher.ptr, scanning_mode != "passive")
            token_rx = w.watcher_add_received(watcher.ptr, received_delegate.ptr)
            token_stop = w.watcher_add_stopped(watcher.ptr, stopped_delegate.ptr)
            w.watcher_start(watcher.ptr)
            await done.wait()
        finally:
            timeout_handle.cancel()
            try:
                w.watcher_stop(watcher.ptr)
            except Exception:
                pass
            for token, remover in ((token_stop, w.watcher_remove_stopped), (token_rx, w.watcher_remove_received)):
                if token is not None:
                    try:
                        remover(watcher.ptr, token)
                    except Exception:
                        pass
            watcher.release()

        return [*devices.values()]


async def _await_ptr(operation_ptr, handler_iid, timeout: float, op_name: str, *, get_results: bool = True):
    op = w.ComPtr(operation_ptr)
    loop = asyncio.get_running_loop()
    done = asyncio.Event()
    status, timed_out = w.ASYNC_STARTED, False

    def on_completed(_sender, raw_status: int) -> None:
        nonlocal status
        status = raw_status
        loop.call_soon_threadsafe(done.set)

    def on_timeout() -> None:
        nonlocal timed_out
        timed_out = True
        done.set()

    handler = w.AsyncOperationCompletedDelegate(handler_iid, on_completed)
    w.asyncop_set_completed(op.ptr, handler.ptr)
    timeout_handle = loop.call_later(timeout, on_timeout)
    try:
        await done.wait()
        if timed_out:
            raise TimeoutError(f"IAsyncOperation timed out: {op_name}")
        if status != w.ASYNC_COMPLETED:
            if status == w.ASYNC_CANCELED:
                raise w.WinRTError(f"IAsyncOperation canceled: {op_name}")
            async_info = op.query_interface(w.IID_IASYNC_INFO)
            try:
                code = w.asyncinfo_get_error_code(async_info.ptr)
            finally:
                async_info.release()
            raise w.WinRTError("IAsyncOperation error %s: 0x%08X" % (op_name, code & 0xFFFFFFFF))
        return w.asyncop_get_results_ptr(op.ptr) if get_results else None
    finally:
        timeout_handle.cancel()
        op.release()


def _format_bdaddr(address: int) -> str:
    return address.to_bytes(6, "big").hex(":").upper()
