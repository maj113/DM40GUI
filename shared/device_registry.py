_METADATA: dict[str, tuple[str, bytes]] = {
    "DM40": ("DM40", b"\x05\x03"),
    "EL15": ("EL15", b"\x07\x03"),
}

FAMILY_MAP: dict[bytes, str] = {
    family: dtype for dtype, (_, family) in _METADATA.items()
}


def guess_device_type(name: str) -> str | None:
    upper = name.upper()
    for dtype, (prefix, _) in _METADATA.items():
        if upper.startswith(prefix):
            return dtype
    return None


def load_handler(dtype: str, app):
    if dtype == "DM40":
        from dm40.app import DM40Handler
        return DM40Handler(app)
    if dtype == "EL15":
        from el15.app import EL15Handler
        return EL15Handler(app)
    raise KeyError(f"Unknown device type: {dtype!r}")
