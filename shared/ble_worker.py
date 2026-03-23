"""BLE transport worker."""

import _thread
import time

from shared import mini_asyncio as asyncio
from shared.nanowinbt.client import NanoClient

_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
_NOTIFY_UUID  = "0000fff1-0000-1000-8000-00805f9b34fb"
_WRITE_UUID   = "0000fff3-0000-1000-8000-00805f9b34fb"

_CMD_DISCOVERY = b"\xaf\xff\xff\x00\x00\x53"
_DISCOVERY_HEADER = b"\xdf\xff\xff\x00"
_FAMILY_MAP = {b"\x05\x03": "DM40", b"\x07\x03": "EL15"}


def probe_device_type(device, timeout: float = 6.0) -> str | None:
    """Connect, send discovery command, return 'DM40'/'EL15' or None.
    Blocking — call from a background thread."""
    result = [None]
    try:
        asyncio.run(_probe(device, timeout, result))
    except Exception:
        pass
    return result[0]


async def _probe(device, timeout, result):
    responses = []
    loop = asyncio.get_running_loop()
    got = asyncio.Event()

    def on_notify(data: bytes):
        responses.append(data)
        loop.call_soon_threadsafe(got.set)

    async with NanoClient(device, timeout=timeout) as client:
        await client.prime_gatt(_SERVICE_UUID, [_NOTIFY_UUID, _WRITE_UUID], 8)
        await client.start_notify(_NOTIFY_UUID, on_notify)
        await client.write_gatt_char(_WRITE_UUID, _CMD_DISCOVERY)

        deadline_handle = loop.call_later(3.0, got.set)
        await got.wait()
        deadline_handle.cancel()

        for r in responses:
            if r.startswith(_DISCOVERY_HEADER) and len(r) >= 7:
                family = _FAMILY_MAP.get(r[5:7])
                if family:
                    result[0] = family
                    break

        try:
            await client.stop_notify(_NOTIFY_UUID)
        except Exception:
            pass


class BleWorker:
    __slots__ = (
        "device", "_on_packet", "_on_tx", "_on_status", "_on_error",
        "_on_connected", "_on_disconnected", "_stopping", "alive",
        "_pending_cmd", "_loop", "_io_event",
        "_poll_cmd", "_init_cmd", "_notify_hook", "_write_buf_size",
    )

    def __init__(
        self,
        device,
        *,
        poll_cmd: bytes,
        init_cmd: bytes | None = None,
        notify_hook=None,
        write_buf_size: int = 20,
        on_packet=None,
        on_tx=None,
        on_status=None,
        on_error=None,
        on_connected=None,
        on_disconnected=None,
    ):
        self.device = device
        self._poll_cmd = poll_cmd
        self._init_cmd = init_cmd
        self._notify_hook = notify_hook
        self._write_buf_size = write_buf_size
        self._on_packet = on_packet
        self._on_tx = on_tx
        self._on_status = on_status
        self._on_error = on_error
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._stopping = False
        self.alive = True
        self._pending_cmd: bytes | None = None
        self._loop = None
        self._io_event = None
        try:
            _thread.start_new_thread(self.run, ())
        except Exception:
            self.alive = False
            raise

    def stop(self) -> None:
        self._stopping = True
        self._wake()

    def _wake(self) -> None:
        loop = self._loop
        io_event = self._io_event
        if loop is not None and io_event is not None:
            loop.call_soon_threadsafe(io_event.set)

    def set_command(self, payload: bytes) -> None:
        self._pending_cmd = payload
        self._wake()

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        try:
            loop.run_until_complete(self._main())
        except Exception as exc:
            on_error = self._on_error
            if on_error:
                on_error(f"Worker failed: {exc!r}")
        finally:
            self._loop = None
            self._io_event = None
            loop.close()
            self.alive = False

    async def _main(self) -> None:
        device       = self.device
        address      = device.address
        on_packet    = self._on_packet
        on_tx        = self._on_tx
        on_status    = self._on_status
        on_error     = self._on_error
        on_connected = self._on_connected
        on_disconn   = self._on_disconnected
        poll_cmd     = self._poll_cmd
        init_cmd     = self._init_cmd
        notify_hook  = self._notify_hook

        last_rx = 0.0
        no_data_emitted = False
        disconnected = False
        disconnect_notified = False
        read_ready = True
        io_event = asyncio.Event()
        self._io_event = io_event

        def _notify_disconnect() -> None:
            nonlocal disconnect_notified
            if disconnect_notified:
                return
            disconnect_notified = True
            if on_status:
                on_status(f"disconnected — {address}")
            if on_disconn:
                on_disconn(address)

        def on_notify(data: bytes) -> None:
            nonlocal last_rx, no_data_emitted, read_ready
            last_rx = time.monotonic()
            no_data_emitted = False
            read_ready = True
            io_event.set()
            if (notify_hook is None or notify_hook(data)) and on_packet:
                on_packet(data)

        def on_disconnect() -> None:
            nonlocal disconnected
            disconnected = True
            self._wake()
            _notify_disconnect()

        if on_status:
            on_status(f"connecting — {address}")
        async with NanoClient(device, disconnected_callback=on_disconnect) as client:
            await client.prime_gatt(_SERVICE_UUID, [_NOTIFY_UUID, _WRITE_UUID], self._write_buf_size)
            await client.start_notify(_NOTIFY_UUID, on_notify)

            if init_cmd is not None:
                try:
                    await client.write_gatt_char(_WRITE_UUID, init_cmd)
                except Exception as exc:
                    if on_error:
                        on_error(f"Init failed: {exc!r}")
                    return
                if on_tx:
                    on_tx(init_cmd)

            if on_status:
                on_status(f"connected — {address}")
            if on_connected:
                on_connected(address)
            io_event.set()

            try:
                while not self._stopping:
                    if disconnected:
                        _notify_disconnect()
                        break

                    await io_event.wait()
                    io_event.clear()
                    if self._stopping or disconnected:
                        break

                    if read_ready:
                        cmd = self._pending_cmd
                        self._pending_cmd = None
                        payload = poll_cmd if cmd is None else cmd
                        try:
                            await client.write_gatt_char(_WRITE_UUID, payload)
                        except Exception as exc:
                            if on_error:
                                on_error(f"{'Write' if cmd else 'Poll'} failed: {exc!r}")
                            return
                        if cmd is not None and on_tx:
                            on_tx(payload)
                        read_ready = False

                    if last_rx and not no_data_emitted and (time.monotonic() - last_rx) > 2.0:
                        if on_status:
                            on_status(f"connected — {address} — (no data)")
                        no_data_emitted = True

            finally:
                try:
                    await client.stop_notify(_NOTIFY_UUID)
                except Exception:
                    pass
                _notify_disconnect()
