"""EL15 protocol constants and packet parsing."""
import ctypes as _ct

HEADER   = b"\xdf\x07\x03\x08"
# Pre-computed poll packet (CMD_QUERY prefix + CRC byte 0x3F)
POLL_PKT = b"\xaf\x07\x03\x08\x00\x3f"

CMD_LOAD_ON  = b"\xaf\x07\x03\x09\x01\x04"
CMD_LOAD_OFF = b"\xaf\x07\x03\x09\x01\x00"
CMD_LOCK     = b"\xaf\x07\x03\x09\x01\x01"
CMD_MODE_CC  = b"\xaf\x07\x03\x03\x01\x01"
CMD_MODE_CAP = b"\xaf\x07\x03\x03\x01\x02"
CMD_MODE_CV  = b"\xaf\x07\x03\x03\x01\x09"
CMD_MODE_DCR = b"\xaf\x07\x03\x03\x01\x0a"
CMD_MODE_CR  = b"\xaf\x07\x03\x03\x01\x11"
CMD_MODE_CP  = b"\xaf\x07\x03\x03\x01\x19"

MODE_CC  = 0x01
MODE_CAP = 0x02
MODE_CV  = 0x09
MODE_DCR = 0x0A
MODE_CR  = 0x11
MODE_CP  = 0x19

MODE_NAMES = {
    MODE_CC:  "CC",
    MODE_CAP: "CAP",
    MODE_CV:  "CV",
    MODE_DCR: "DCR",
    MODE_CR:  "CR",
    MODE_CP:  "CP",
}

# (unit_str, decimal_places, label)
MODE_SETPOINT_INFO = {
    MODE_CC:  ("A",  3, "Current"),
    MODE_CAP: ("A",  3, "Current"),
    MODE_CV:  ("V",  3, "Voltage"),
    MODE_DCR: ("A",  3, "Current"),
    MODE_CR:  ("Ω",  1, "Resistance"),
    MODE_CP:  ("W",  2, "Power"),
}


def build_set_setpoint_cmd(value: float) -> bytes:
    """Return a 9-byte setpoint command prefix (caller appends CRC)."""
    f = _ct.c_float(value)
    return b"\xaf\x07\x03\x04\x04" + _ct.string_at(_ct.addressof(f), 4)


class EL15Status:
    __slots__ = (
        "raw", "crc_ok", "valid",
        "voltage", "current", "power", "runtime", "temperature", "setpoint",
        "mode", "mode_name", "fan_speed", "load_on",
        "setpoint_unit", "setpoint_decimals", "setpoint_label",
    )

    def __init__(self):
        self.raw = ""
        self.crc_ok = False
        self.valid = False
        self.voltage = self.current = self.power = 0.0
        self.runtime = 0
        self.temperature = self.setpoint = 0.0
        self.mode = MODE_CC
        self.mode_name = "---"
        self.fan_speed = 0
        self.load_on = False
        self.setpoint_unit = "A"
        self.setpoint_decimals = 3
        self.setpoint_label = "Current"


def parse_status_packet(data: bytes) -> EL15Status:
    """Parse a 28-byte EL15 status notification into EL15Status."""
    s = EL15Status()
    s.raw   = data.hex(" ").upper()
    s.crc_ok = (sum(data) & 0xFF) == 0
    if len(data) < 28 or data[:4] != HEADER:
        return s
    s.voltage     = _ct.c_float.from_buffer_copy(data,  7).value
    s.current     = _ct.c_float.from_buffer_copy(data, 11).value
    s.runtime     = _ct.c_int32.from_buffer_copy(data, 15).value
    s.temperature = _ct.c_float.from_buffer_copy(data, 19).value
    s.setpoint    = _ct.c_float.from_buffer_copy(data, 23).value
    s.power       = s.voltage * s.current
    s.mode        = data[5] & 0x0F
    s.fan_speed   = data[5] >> 4
    s.load_on     = data[6] != 0
    s.mode_name   = MODE_NAMES.get(s.mode, f"?{s.mode:02X}")
    info = MODE_SETPOINT_INFO.get(s.mode, ("?", 3, "Setpoint"))
    s.setpoint_unit, s.setpoint_decimals, s.setpoint_label = info
    s.valid = True
    return s
