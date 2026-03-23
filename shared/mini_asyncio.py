import _thread
import time

from _heapq import heappop, heappush


_tls = _thread._local()


class TimerHandle:
    __slots__ = ("_callback", "_args", "_cancelled")

    def __init__(self, callback, args):
        self._callback = callback
        self._args = args
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True


class Future:
    __slots__ = ("_loop", "_done", "_result", "_exception", "_callbacks")

    def __init__(self, loop):
        self._loop = loop
        self._done = False
        self._result = None
        self._exception = None
        self._callbacks = []

    def done(self) -> bool:
        return self._done

    def set_result(self, result):
        if self._done:
            return
        self._done = True
        self._result = result
        callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            self._loop.call_soon(callback, self)

    def set_exception(self, exc):
        if self._done:
            return
        self._done = True
        self._exception = exc
        callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            self._loop.call_soon(callback, self)

    def add_done_callback(self, callback):
        if self._done:
            self._loop.call_soon(callback, self)
            return
        self._callbacks.append(callback)

    def result(self):
        if self._exception is not None:
            raise self._exception
        return self._result

    def __await__(self):
        if not self._done:
            yield self
        return self.result()


class Task(Future):
    __slots__ = ("_coro",)

    def __init__(self, loop, coro):
        super().__init__(loop)
        self._coro = coro
        loop.call_soon(self._step, None, None)

    def _step(self, value, exc):
        if self.done():
            return
        try:
            if exc is not None:
                awaited = self._coro.throw(exc)
            else:
                awaited = self._coro.send(value)
        except StopIteration as stop:
            self.set_result(stop.value)
            return
        except BaseException as err:
            self.set_exception(err)
            return

        future = self._loop._coerce_awaitable(awaited)
        future.add_done_callback(self._wakeup)

    def _wakeup(self, future):
        try:
            result = future.result()
        except BaseException as exc:
            self._loop.call_soon(self._step, None, exc)
        else:
            self._loop.call_soon(self._step, result, None)


class Event:
    __slots__ = ("_flag", "_waiters")

    def __init__(self):
        self._flag = False
        self._waiters = []

    def set(self) -> None:
        self._flag = True
        waiters, self._waiters = self._waiters, []
        for waiter in waiters:
            waiter.set_result(True)

    def clear(self) -> None:
        self._flag = False

    async def wait(self) -> bool:
        if self._flag:
            return True
        loop = get_running_loop()
        waiter = Future(loop)
        self._waiters.append(waiter)
        return await waiter


class AbstractEventLoop:
    __slots__ = ("_ready", "_timers", "_threadsafe", "_ts_lock", "_sequence")

    def __init__(self):
        self._ready = []
        self._timers = []
        self._threadsafe = []
        self._ts_lock = _thread.allocate_lock()
        self._sequence = 0

    def call_soon(self, callback, *args):
        self._ready.append((callback, args))

    def call_soon_threadsafe(self, callback, *args):
        with self._ts_lock:
            self._threadsafe.append((callback, args))

    def call_later(self, delay, callback, *args):
        when = time.monotonic() + max(0, delay)
        self._sequence += 1
        handle = TimerHandle(callback, args)
        item = (when, self._sequence, handle)
        heappush(self._timers, item)
        return handle

    def run_until_complete(self, coro):
        _tls.running_loop = self
        try:
            task = Task(self, coro)
            while not task.done():
                self._run_once()
            return task.result()
        finally:
            _tls.running_loop = None

    def close(self) -> None:
        self._ready.clear()
        self._timers.clear()

    def _coerce_awaitable(self, awaited):
        if isinstance(awaited, Future):
            return awaited
        if hasattr(awaited, "__await__"):
            return Task(self, awaited)
        immediate = Future(self)
        immediate.set_result(awaited)
        return immediate

    def _run_once(self) -> None:
        with self._ts_lock:
            if self._threadsafe:
                self._ready.extend(self._threadsafe)
                self._threadsafe = []

        now = time.monotonic()
        while self._timers and self._timers[0][0] <= now:
            _, _, handle = heappop(self._timers)
            if handle._cancelled:
                continue
            self._ready.append((handle._callback, handle._args))

        if self._ready:
            batch, self._ready = self._ready, []
            for callback, args in batch:
                callback(*args)
            return

        sleep_for = 0.001
        if self._timers:
            sleep_for = self._timers[0][0] - now
            if sleep_for < 0.0:
                sleep_for = 0.0
            elif sleep_for > 0.01:
                sleep_for = 0.01
        time.sleep(sleep_for)


def new_event_loop():
    return AbstractEventLoop()


def get_running_loop():
    loop = getattr(_tls, "running_loop", None)
    if loop is None:
        raise RuntimeError("no running event loop")
    return loop


def run(coro):
    loop = new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()