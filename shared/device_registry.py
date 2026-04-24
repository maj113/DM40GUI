"""Device registry: one place to declare a new handler.

Each entry maps a device-type string to:
    (handler_module, handler_class, name_prefix, discovery_family_bytes)

- `handler_module` / `handler_class` are imported lazily so unused handlers
  stay out of the frozen binary's startup path.
- `name_prefix` is matched case-insensitively against the BLE advertised name.
- `discovery_family_bytes` are bytes 5-6 of the reply to the probe command
  sent by `shared.ble_worker.probe_device_type`.
"""

DEVICE_REGISTRY: dict[str, tuple[str, str, str, bytes]] = {
    "DM40": ("dm40.app", "DM40Handler", "DM40", b"\x05\x03"),
    "EL15": ("el15.app", "EL15Handler", "EL15", b"\x07\x03"),
}


def guess_device_type(name: str) -> str | None:
    upper = name.upper()
    for dtype, (_, _, prefix, _) in DEVICE_REGISTRY.items():
        if upper.startswith(prefix):
            return dtype
    return None


def load_handler(dtype: str, app):
    module_name, class_name, _, _ = DEVICE_REGISTRY[dtype]
    module = __import__(module_name, fromlist=(class_name,))
    return getattr(module, class_name)(app)


FAMILY_MAP: dict[bytes, str] = {
    family: dtype for dtype, (_, _, _, family) in DEVICE_REGISTRY.items()
}
