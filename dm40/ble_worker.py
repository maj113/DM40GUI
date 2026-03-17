"""BLE transport worker for DM40."""

import _thread
import time

from . import mini_asyncio as asyncio

from .nanowinbt.client import NanoClient

from .parsing import MODEL, MODEL_TABLE
from .protocol_constants import (
    CMD_ID,
    CMD_READ,
    NOTIFY_UUID,
    SERVICE_UUID,
    WRITE_UUID,
)


class BleWorker:
    __slots__ = (
        "device", "_on_packet", "_on_tx", "_on_status", "_on_error",
        "_on_connected", "_on_disconnected", "_stopping", "alive",
        "_pending_cmd", "_loop", "_io_event",
    )
    MODEL_PREFIX = b"\xdf\x05\x03\x08\x14"

    def __init__(
        self,
        device,
        *,
        on_packet=None,
        on_tx=None,
        on_status=None,
        on_error=None,
        on_connected=None,
        on_disconnected=None,
    ):
        self.device = device
        self._on_packet = on_packet
        self._on_tx = on_tx
        self._on_status = on_status
        self._on_error = on_error
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._stopping = False
        self.alive = False
        self._pending_cmd: bytes | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._io_event: asyncio.Event | None = None

        self.alive = True
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
            self._emit(self._on_error, f"Worker failed: {exc!r}")
        finally:
            self._loop = None
            self._io_event = None
            loop.close()
            self.alive = False

    @staticmethod
    def _emit(callback, *args) -> None:
        if callback is not None:
            callback(*args)

    async def _main(self) -> None:
        device = self.device
        address = device.address

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
            self._emit(self._on_status, f"disconnected — {address}")
            self._emit(self._on_disconnected, address)

        def on_notify(data: bytes) -> None:
            nonlocal last_rx, no_data_emitted, read_ready
            last_rx = time.monotonic()
            no_data_emitted = False
            read_ready = True
            io_event.set()

            if data.startswith(self.MODEL_PREFIX):
                idx = data[9] - ord("A")
                if 0 <= idx < len(MODEL_TABLE):
                    MODEL.model_name, MODEL.device_counts = MODEL_TABLE[idx]
                return

            self._emit(self._on_packet, data)

        def on_disconnect() -> None:
            nonlocal disconnected
            disconnected = True
            self._wake()
            _notify_disconnect()

        self._emit(self._on_status, f"connecting — {address}")
        async with NanoClient(device, disconnected_callback=on_disconnect) as client:
            await client.prime_gatt(SERVICE_UUID, [NOTIFY_UUID, WRITE_UUID])
            await client.start_notify(
                NOTIFY_UUID,
                on_notify,
            )

            try:
                await client.write_gatt_char(WRITE_UUID, CMD_ID)
            except Exception as exc:
                self._emit(self._on_error, f"ID request failed: {exc!r}")
                return
            self._emit(self._on_status, f"connected — {address}")
            self._emit(self._on_connected, address)
            self._emit(self._on_tx, CMD_ID)
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
                        payload = cmd if cmd is not None else CMD_READ

                        try:
                            await client.write_gatt_char(WRITE_UUID, payload)
                        except Exception as exc:
                            self._emit(self._on_error, f"{'Write' if cmd else 'Read'} failed: {exc!r}")
                            return

                        if cmd is not None:
                            self._emit(self._on_tx, payload)
                        read_ready = False

                    if last_rx and not no_data_emitted and (time.monotonic() - last_rx) > 2.0:
                        self._emit(self._on_status, f"connected — {address} — (no data)")
                        no_data_emitted = True

            finally:
                try:
                    await client.stop_notify(
                        NOTIFY_UUID,
                    )
                except Exception:
                    pass
                _notify_disconnect()
