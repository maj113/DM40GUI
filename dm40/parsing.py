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

    def __init__(
        self,
        raw="",
        kind="---",
        range=None,
        display_unit="",
        value_str="---",
        norm_value=None,
        vertical_pad=0.0,
        decimals=2,
        sec_val=None,
        sec_unit="",
        third_val=None,
        third_unit="",
        overload=False,
        crc_ok=False,
    ):
        self.raw = raw
        self.kind = kind
        self.range = range
        self.display_unit = display_unit
        self.value_str = value_str
        self.norm_value = norm_value
        self.vertical_pad = vertical_pad
        self.decimals = decimals
        self.sec_val = sec_val
        self.sec_unit = sec_unit
        self.third_val = third_val
        self.third_unit = third_unit
        self.overload = overload
        self.crc_ok = crc_ok


MODEL_TABLE = (("DM40A", 40000), ("DM40B", 50000), ("DM40C", 60000))


def resolve_slot_scale(slot: str, kind: str, sign_flag: int):
    scale_flag = sign_flag & 0xFE
    if slot == "FREQ":
        return FREQ_SCALE_MAP[scale_flag]
    factor = MODEL.device_counts / 60000.0
    if kind == "CAP" and slot == "M1":
        info = CAP_SCALE_MAP[scale_flag]
    elif slot in ("M1", "COMB", "DC", "AC") and (kind.startswith("V") or kind == "DIODE"):
        info = ALT_SCALE_MAP[scale_flag]
    elif slot in ("M1", "COMB", "DC", "AC") and kind.startswith("A"):
        info = AMP_SCALE_MAP[scale_flag]
    elif slot == "M1" and kind in ("RES", "RES_ONLINE", "CONT"):
        info = RES_SCALE_MAP[scale_flag]
    elif slot == "TC" and kind == "TEMP":
        info = (6000.0, "°C", 1.0, 1)
    elif slot == "RES" and kind == "DIODE":
        return 6000.0 * factor, "Ω", 1.0, 1
    else:
        return None

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
    sign = -1 if (sign_flag & 0x01) else 1

    if not (resolved := resolve_slot_scale(slot_type, kind, sign_flag)):
        if slot_type in ("DUTY", "TF", "TI"):
            val = counts * 0.1
            return f"{val:.1f}", "%" if slot_type == "DUTY" else ("°F" if slot_type == "TF" else "°C")
        return "", ""

    full_scale, disp_unit, disp_mul, decimals = resolved
    scale = full_scale / MODEL.device_counts
    val_disp = (counts * scale * disp_mul) * sign
    return f"{val_disp:.{decimals}f}", disp_unit


def parse_measurement_for_ui(data: bytes) -> Measurement:
    m = Measurement(raw=data.hex(" ").upper())
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
        m.norm_value = sign * m1 * (fs1 / eff_counts)
        m.value_str = f"{m.norm_value * mul1:.{dec1}f}"

    if not rng_name.startswith("AUTO"):
        m.range = f"{(fs1 * mul1):.4g}{unit1}"

    if len(slots) > 1 and m2 != 0xFFFF:
        m.sec_val, m.sec_unit = process_slot(slots[1], m2, s1, kind)
    if len(slots) > 2 and m3 != 0xFFFF:
        m.third_val, m.third_unit = process_slot(slots[2], m3, s2, kind)

    return m
