"""Packet parsing and scale conversion for DM40."""

from .protocol_constants import (
    ALT_SCALE_MAP,
    AMP_SCALE_MAP,
    CAP_SCALE_MAP,
    FLAG_INFO,
    FREQ_SCALE_MAP,
    HEADER,
    MODE_SLOT_MAP,
    RES_SCALE_MAP,
)

# Packet byte offsets (16-byte measurement frame, HEADER at [0:4]).
_FLAG_BYTE = 5          # mode/range flag
_STATUS_BYTE = 6        # device status (range, hold, auto, battery)
_M3_LO, _M3_HI = 10, 11  # slot M3 counts (little-endian u16)
_M2_LO, _M2_HI = 12, 13  # slot M2 counts
_M1_LO, _M1_HI = 14, 15  # slot M1 counts
_SCALE_M1 = -8          # sign/scale byte for slot M1 (from end)
_SCALE_M2 = -9          # sign/scale byte for slot M2
_SCALE_M3 = -10         # sign/scale byte for slot M3


class ModelInfo:
    __slots__ = ("model_name", "device_counts")

    def __init__(self, model_name="DM40C", device_counts=60000):
        self.model_name = model_name
        self.device_counts = device_counts


MODEL = ModelInfo()


class Measurement:
    __slots__ = (
        "raw",
        "kind",
        "range",
        "display_unit",
        "value_str",
        "norm_value",
        "vertical_pad",
        "decimals",
        "sec_val",
        "sec_unit",
        "third_val",
        "third_unit",
        "overload",
        "crc_ok",
    )

    def __init__(self):
        self.raw = ""
        self.kind = "---"
        self.range = ""
        self.display_unit = ""
        self.value_str = "---"
        self.norm_value = None  # type: ignore[assignment]
        self.vertical_pad = 0.0
        self.decimals = 2
        self.sec_val = ""
        self.sec_unit = ""
        self.third_val = ""
        self.third_unit = ""
        self.overload = False
        self.crc_ok = False


MODEL_TABLE = (("DM40A", 40000), ("DM40B", 50000), ("DM40C", 60000))


def resolve_slot_scale(slot: str, kind: str, sign_flag: int):
    scale_flag = sign_flag & 0xFE

    if slot == "FREQ":
        return FREQ_SCALE_MAP[scale_flag]

    if slot in ("M1", "DC", "AC"):
        if kind.startswith("V") or kind == "DIODE":
            info = ALT_SCALE_MAP[scale_flag]
        elif kind.startswith("A"):
            info = AMP_SCALE_MAP[scale_flag]
        elif kind in ("RES", "RES_ONLINE", "CONT"):
            info = RES_SCALE_MAP[scale_flag]
        elif kind == "CAP":
            info = CAP_SCALE_MAP[scale_flag]
        else:
            return None
    elif slot == "TC" and kind == "TEMP":
        info = (6000.0, "°C", 1.0, 1)
    elif slot == "RES" and kind == "DIODE":
        info = (6000.0, "Ω", 1.0, 1)
    else:
        return None

    factor = MODEL.device_counts / 60000.0
    fs_base, unit, mul, dec = info
    return fs_base * factor, unit, mul, dec


def parse_device_status(data: bytes) -> tuple:
    status = data[_STATUS_BYTE]
    return (
        status & 0x07,
        (status & 0x08) != 0,
        (status & 0x40) != 0,
        (status & 0x80) != 0,
    )


def process_slot(slot_type: str, counts: int, sign_flag: int, kind: str):
    ol = counts == 0xFFFF

    if resolved := resolve_slot_scale(slot_type, kind, sign_flag):
        full_scale, disp_unit, disp_mul, decimals = resolved
        if ol:
            return "OL", disp_unit
        sign = -1 if (sign_flag & 1) else 1
        val_disp = counts * (full_scale / MODEL.device_counts) * disp_mul * sign
        return "%.*f" % (decimals, val_disp), disp_unit

    if slot_type in ("DUTY", "TF", "TI"):
        val_str = "OL" if ol else "%.1f" % (counts * 0.1)
        if slot_type == "DUTY":
            return val_str, "%"
        return val_str, "°F" if slot_type == "TF" else "°C INT"

    return "", ""

def parse_measurement_for_ui(data: bytes) -> Measurement:
    m = Measurement()
    m.raw = data.hex(" ").upper()
    m.crc_ok = ((sum(data) & 0xFF) == 0) if data else False
    if len(data) < 16 or not data.startswith(HEADER):
        return m

    m1, m2, m3 = (
        (data[_M1_HI] << 8) | data[_M1_LO],
        (data[_M2_HI] << 8) | data[_M2_LO],
        (data[_M3_HI] << 8) | data[_M3_LO],
    )
    
    # We deliberately use direct indexing to fail fast on unknown flags
    kind, rng_name = FLAG_INFO[data[_FLAG_BYTE]]

    m.kind, m.range, m.overload = kind, rng_name, (m1 == 0xFFFF)
    slots = MODE_SLOT_MAP[kind]
    s0, s1, s2 = data[_SCALE_M1], data[_SCALE_M2], data[_SCALE_M3]

    if not (res1 := resolve_slot_scale(slots[0], kind, s0)):
        return m

    fs1, unit1, mul1, dec1 = res1
    m.display_unit, m.decimals = unit1, dec1
    eff_counts = MODEL.device_counts / 10 if kind == "CAP" else MODEL.device_counts
    m.vertical_pad = 50 * (fs1 / eff_counts)

    if not m.overload:
        sign = -1 if (s0 & 0x01) else 1
        m.norm_value = sign * m1 * (fs1 / eff_counts)  # type: ignore[assignment]
        m.value_str = "%.*f" % (dec1, m.norm_value * mul1)  # type: ignore[operator]

    if not rng_name.startswith("AUTO"):
        m.range = f"{(fs1 * mul1):.4g}{unit1}"

    if len(slots) > 1:
        m.sec_val, m.sec_unit = process_slot(slots[1], m2, s1, kind)
    if len(slots) > 2:
        m.third_val, m.third_unit = process_slot(slots[2], m3, s2, kind)

    return m
