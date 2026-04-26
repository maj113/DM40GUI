import ctypes

from .. import mini_asyncio as asyncio
from . import ctypes_winrt as w
from .ctypes_com import RoSession
from .scanner import _await_ptr


_GATT_STATUS_NAMES = ("Success", "Unreachable", "ProtocolError", "AccessDenied")


class NanoClientError(RuntimeError):
    pass


class NanoClient:
    def __init__(self, connect_target, disconnected_callback=None, *, timeout: float = 30.0):
        self._target = connect_target
        self._disconnected_callback = disconnected_callback
        self._timeout = timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ro: RoSession | None = None
        self._device: w.ComPtr | None = None
        self._chars: dict[str, w.ComPtr] = {}
        self._notify_tokens: dict = {}
        self._status_token = None
        self._status_delegate = None
        self._write_buffer: w.ComPtr | None = None
        self._write_buffer_ptr = None
        self._write_buffer_data_ptr = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    def _require_char(self, char_uuid: str) -> w.ComPtr:
        if self._device is None:
            raise NanoClientError("Not connected")
        char = self._chars.get(char_uuid)
        if char is None:
            raise NanoClientError(f"Characteristic not primed: {char_uuid}")
        return char

    async def connect(self) -> None:
        if self._device is not None:
            return
        bt_addr = self._target.bluetooth_address
        if not bt_addr:
            raise NanoClientError("Connection requires bluetooth_address")

        self._loop = asyncio.get_running_loop()
        self._ro = RoSession()
        self._ro.initialize()

        statics = w.get_activation_factory("Windows.Devices.Bluetooth.BluetoothLEDevice", w.IID_BLUETOOTH_LE_DEVICE_STATICS)
        try:
            device_ptr = await _await_ptr(
                w.btle_statics_from_bluetooth_address_async(statics.ptr, bt_addr),
                w.IID_ASYNC_COMPLETED_HANDLER_BLUETOOTH_LE_DEVICE,
                min(self._timeout, 8.0),
                "client.from_addr",
            )
        finally:
            statics.release()

        if not device_ptr:
            raise NanoClientError("Device not found for address: %#x" % bt_addr)
        self._device = w.ComPtr(device_ptr)
        w.btle_device6_request_throughput_params(device_ptr)
        self._register_disconnect_handler()

    async def disconnect(self) -> None:
        self._unregister_disconnect_handler()
        self._release_all()

    async def prime_gatt(self, service_uuid: str, char_uuids: list[str], write_buffer_size: int) -> None:
        device = self._device
        if device is None:
            raise NanoClientError("Not connected")

        missing = [u for u in char_uuids if u not in self._chars]
        if not missing:
            return

        target_service = w._guid(service_uuid)
        ptrs = []
        try:
            device3 = device.query_interface(w.IID_BLUETOOTH_LE_DEVICE3); ptrs.append(device3)
            services_result_ptr = await _await_ptr(
                w.btle_device3_get_gatt_services_for_uuid_uncached_async(device3.ptr, target_service),
                w.IID_ASYNC_COMPLETED_HANDLER_GATT_DEVICE_SERVICES_RESULT,
                5.0,
                "client.prime.services",
            )
            services_result = w.ComPtr(services_result_ptr); ptrs.append(services_result)
            svc_status = w.gatt_services_result_get_status(services_result.ptr)
            if svc_status != 0:
                conn_status = w.btle_device_get_connection_status(device.ptr)
                status_name = (
                    _GATT_STATUS_NAMES[svc_status]
                    if 0 <= svc_status < len(_GATT_STATUS_NAMES)
                    else "Unknown"
                )
                raise NanoClientError(
                    "GATT service query failed: "
                    f"status={svc_status} ({status_name}), "
                    f"connection={'Connected' if conn_status == 1 else 'Disconnected'}, "
                    f"service_uuid={service_uuid}, "
                    f"missing={missing}, "
                    f"bt_address={self._target.bluetooth_address:#x}"
                )
            services_view = w.ComPtr(w.gatt_services_result_get_services(services_result.ptr)); ptrs.append(services_view)
            if w.vector_view_get_size(services_view.ptr) == 0:
                raise NanoClientError(f"Service not found: {service_uuid}")
            service = w.ComPtr(w.vector_view_get_at(services_view.ptr, 0)); ptrs.append(service)
            service3 = service.query_interface(w.IID_GATT_DEVICE_SERVICE3); ptrs.append(service3)

            chars_result_ptr = await _await_ptr(
                w.gatt_service3_get_characteristics_async(service3.ptr),
                w.IID_ASYNC_COMPLETED_HANDLER_GATT_CHARACTERISTICS_RESULT,
                3.5,
                "client.prime.chars",
            )
            chars_result = w.ComPtr(chars_result_ptr); ptrs.append(chars_result)
            if w.gatt_characteristics_result_get_status(chars_result.ptr) != 0:
                raise NanoClientError("Characteristic query failed")
            chars_view = w.ComPtr(w.gatt_characteristics_result_get_characteristics(chars_result.ptr)); ptrs.append(chars_view)
            count = w.vector_view_get_size(chars_view.ptr)
            targets = {w._bguid(u): u for u in missing}
            for i in range(count):
                cp = w.vector_view_get_at(chars_view.ptr, i)
                matched = targets.pop(bytes(w.gatt_characteristic_get_uuid(cp)), None)
                if matched is not None:
                    self._chars[matched] = w.ComPtr(cp)
                else:
                    w.release_ptr(cp)
            if targets:
                raise NanoClientError(f"Characteristics not found: {[*targets.values()]}")
        finally:
            for p in reversed(ptrs):
                p.release()

        self._write_buffer = w.ComPtr(w.buffer_factory_create(write_buffer_size))
        self._write_buffer_ptr = self._write_buffer.ptr
        self._write_buffer_data_ptr = w.buffer_get_data_ptr(self._write_buffer_ptr)

    async def write_gatt_char(self, char_uuid: str, data) -> None:
        char = self._require_char(char_uuid)
        ctypes.memmove(self._write_buffer_data_ptr, data, len(data))  # type: ignore[arg-type]
        w.buffer_set_length(self._write_buffer_ptr, len(data))
        await _await_ptr(
            w.gatt_characteristic_write_value_with_option_async(
                char.ptr,
                self._write_buffer_ptr,
                w.GATT_WRITE_OPTION_WITHOUT_RESPONSE,
            ),
            w.IID_ASYNC_COMPLETED_HANDLER_GATT_COMM_STATUS,
            self._timeout,
            "client.write",
            get_results=False,
        )

    async def start_notify(self, char_uuid: str, callback) -> None:
        char = self._require_char(char_uuid)
        if char_uuid in self._notify_tokens:
            return
        cccd = w.GATT_CCCD_NOTIFY

        def on_value_changed(_sender, args_ptr) -> None:
            try:
                value_buffer = w.ComPtr(w.gatt_value_changed_args_get_characteristic_value(args_ptr))
                try:
                    payload = w.buffer_to_bytes(value_buffer.ptr)
                finally:
                    value_buffer.release()
            except Exception:
                return
            if self._loop is not None:
                self._loop.call_soon_threadsafe(callback, payload)

        delegate = w.TypedEventHandlerDelegate(w.IID_TYPED_EVENT_HANDLER_GATTCHAR_VALUECHANGED, on_value_changed)
        token = w.gatt_characteristic_add_value_changed(char.ptr, delegate.ptr)

        try:
            await _await_ptr(
                w.gatt_characteristic_write_cccd_async(char.ptr, cccd),
                w.IID_ASYNC_COMPLETED_HANDLER_GATT_COMM_STATUS,
                self._timeout,
                "client.notify.start",
                get_results=False,
            )
        except Exception:
            w.gatt_characteristic_remove_value_changed(char.ptr, token)
            raise

        self._notify_tokens[char_uuid] = (char, token, delegate)

    async def stop_notify(self, char_uuid: str) -> None:
        token_entry = self._notify_tokens.get(char_uuid)
        if token_entry is None:
            return

        await _await_ptr(
            w.gatt_characteristic_write_cccd_async(token_entry[0].ptr, w.GATT_CCCD_NONE),
            w.IID_ASYNC_COMPLETED_HANDLER_GATT_COMM_STATUS,
            self._timeout,
            "client.notify.stop",
            get_results=False,
        )

        del self._notify_tokens[char_uuid]
        w.gatt_characteristic_remove_value_changed(token_entry[0].ptr, token_entry[1])

    def _register_disconnect_handler(self) -> None:
        if self._device is None:
            return

        def on_status_changed(sender_ptr, _args_ptr) -> None:
            if self._loop is None or self._disconnected_callback is None:
                return
            try:
                status = w.btle_device_get_connection_status(sender_ptr)
            except Exception:
                return
            if status != w.BLUETOOTH_CONNECTION_STATUS_CONNECTED:
                self._loop.call_soon_threadsafe(self._disconnected_callback)

        delegate = w.TypedEventHandlerDelegate(w.IID_TYPED_EVENT_HANDLER_BLUETOOTHLEDEVICE_INSPECTABLE, on_status_changed)
        self._status_token = w.btle_device_add_connection_status_changed(self._device.ptr, delegate.ptr)
        self._status_delegate = delegate

    def _unregister_disconnect_handler(self) -> None:
        if self._device is not None and self._status_token is not None:
            try:
                w.btle_device_remove_connection_status_changed(self._device.ptr, self._status_token)
            except Exception:
                pass
        self._status_delegate = None
        self._status_token = None

    def _release_all(self) -> None:
        if self._write_buffer is not None:
            try: self._write_buffer.release()
            except Exception: pass
        self._write_buffer = None
        self._write_buffer_ptr = None
        self._write_buffer_data_ptr = None

        for char, token, _delegate in self._notify_tokens.values():
            try: w.gatt_characteristic_remove_value_changed(char.ptr, token)
            except Exception: pass
        self._notify_tokens.clear()

        for c in self._chars.values():
            try: c.release()
            except Exception: pass
        self._chars.clear()

        if self._device is not None:
            try: self._device.release()
            except Exception: pass
        self._device = None

        if self._ro is not None:
            try: self._ro.uninitialize()
            except Exception: pass
        self._ro = None
