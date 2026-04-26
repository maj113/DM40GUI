"""EL15 protocol constants and packet parsing."""

HEADER   = b"\xdf\x07\x03\x08"
# Pre-computed poll packet (CMD_QUERY prefix + CRC byte 0x3F)
POLL_PKT = b"\xaf\x07\x03\x08\x00\x3f"

_SETPOINT_PREFIX = b"\xaf\x07\x03\x04\x04"
_setpoint_fbuf = bytearray(4)
_setpoint_fview = memoryview(_setpoint_fbuf).cast('f')

CMD_LOAD_ON  = b"\xaf\x07\x03\x09\x01\x04"
CMD_LOAD_OFF = b"\xaf\x07\x03\x09\x01\x00"
CMD_LOCK     = b"\xaf\x07\x03\x09\x01\x01"
CMD_MODE_PREFIX = b"\xaf\x07\x03\x03\x01"

MODE_CC       = 0x01
MODE_CAP      = 0x02
MODE_DT       = 0x03
MODE_ADV      = 0x04
MODE_CV       = 0x09
MODE_DCR      = 0x0A
MODE_POWER    = 0x0B
MODE_ADV_SCAN = 0x0C
MODE_POWER_RPT = 0x0D
MODE_CR       = 0x11
MODE_CP       = 0x19

MODE_NAMES = {
    MODE_CC:       "CC",
    MODE_CAP:      "CAP",
    MODE_DT:       "POW [DT]",
    MODE_ADV:      "ADV [L]",
    MODE_CV:       "CV",
    MODE_DCR:      "DCR",
    MODE_POWER:    "POW [A]",
    MODE_ADV_SCAN: "ADV [S]",
    MODE_POWER_RPT: "POW [RPT]",
    MODE_CR:       "CR",
    MODE_CP:       "CP",
}

# (unit_str, decimal_places, label)
MODE_SETPOINT_INFO = {
    MODE_CC:       ("A",  3, "Current"),
    MODE_CAP:      ("A",  3, "Current"),
    MODE_CV:       ("V",  3, "Voltage"),
    MODE_DCR:      ("A",  3, "Current"),
    MODE_CR:       ("Ω",  1, "Resistance"),
    MODE_CP:       ("W",  2, "Power"),
    MODE_ADV:      ("",   3, ""),
    MODE_POWER:    ("",   3, ""),
    MODE_DT:       ("",   3, ""),
    MODE_ADV_SCAN: ("",   3, ""),
    MODE_POWER_RPT: ("",  3, ""),
}


def build_set_setpoint_cmd(value: float) -> bytes:
    _setpoint_fview[0] = value
    return _SETPOINT_PREFIX + bytes(_setpoint_fbuf)


# Status byte 6 bit layout: bit1=load, bit2=lock; upper nibble=protection code
_STATUS_LOAD_BIT = 0x02
_STATUS_LOCK_BIT = 0x04
# Status byte 5 layout: bits 0-4 = mode (bit2 is warning flag), bits 5-7 = fan speed
_MODE_MASK = 0x1F
_B5_WARN_FLAG = 0x06   # bits 1+2 are both set when protection has tripped
FAN_SPEED_MAX = 5

# Upper nibble of byte6 when _B5_WARN_FLAG is set
_WARN_NAMES = {0x6: "REV", 0x9: "UVP"}


class EL15Status:
    __slots__ = (
        "raw", "crc_str", "valid",
        "voltage", "current", "power", "runtime", "temperature", "setpoint",
        "energy_wh", "capacity_ah",
        "dcr_mohm", "dcr_i1", "dcr_i2",
        "mode", "mode_name", "fan_speed", "load_on", "lock_on", "ready",
        "setpoint_unit", "setpoint_decimals", "setpoint_label",
        "setpoint_in_packet", "warning",
    )

    def __init__(self):
        self.raw = ""
        self.crc_str = ""
        self.valid = False
        self.voltage = self.current = self.power = 0.0
        self.runtime = 0
        self.temperature = self.setpoint = 0.0
        self.energy_wh = self.capacity_ah = 0.0
        self.dcr_mohm = self.dcr_i1 = self.dcr_i2 = 0.0
        self.mode = MODE_CC
        self.mode_name = "---"
        self.fan_speed = 0
        self.load_on = False
        self.lock_on = False
        self.ready = False
        self.setpoint_unit = "A"
        self.setpoint_decimals = 3
        self.setpoint_label = "Current"
        self.setpoint_in_packet = True
        self.warning = ""


def parse_status_packet(data: bytes) -> EL15Status:
    """Parse a 28-byte EL15 status notification into EL15Status."""
    s = EL15Status()
    s.raw   = data.hex(" ").upper()
    s.crc_str = "PASS" if (sum(data) & 0xFF) == 0 else "FAIL"
    if len(data) < 28 or data[:4] != HEADER:
        return s
    mv = memoryview(data)
    s.voltage     = mv[7:11].cast('f')[0]
    s.current     = mv[11:15].cast('f')[0]
    s.runtime     = mv[15:19].cast('i')[0]
    s.power       = s.voltage * s.current
    b5 = data[5]
    b6 = data[6]
    # Bits 1+2 of byte5 are BOTH set when protection has tripped. Each bit
    # individually is part of normal mode encoding (CAP=0x02, DCR=0x0A etc.),
    # so the fault test must require both bits set simultaneously.
    # Bit 0 is the "ready/measuring" flag for CC/CV/CR/CP.
    warn_flag     = (b5 & _B5_WARN_FLAG) == _B5_WARN_FLAG
    raw_mode      = (b5 & (_MODE_MASK & ~_B5_WARN_FLAG)) if warn_flag else (b5 & _MODE_MASK)
    mode          = raw_mode if raw_mode in MODE_NAMES else (raw_mode | 0x01)
    s.mode        = mode
    if warn_flag:
        warn_code = b6 >> 4
        s.warning = _WARN_NAMES.get(warn_code, "PROT %X" % warn_code)
        s.ready   = False
    else:
        s.ready   = (raw_mode & 0x01) != 0 or mode in (MODE_CAP, MODE_DCR, MODE_ADV, MODE_POWER, MODE_DT, MODE_ADV_SCAN, MODE_POWER_RPT)
    # Bytes [15:19], [19:23] and [23:27] carry mode-specific measurements.
    #   CC/CV/CR/CP: runtime(i), temperature(f), setpoint(f)
    #   CAP:         runtime(i), energy(f, mWh),   capacity(f, mAh)
    #   DCR:         I1(f, A),   I2(f, A),         resistance(f, m\u03a9); [11:15] unused
    #   ADV/POWER:   unused (V/I only; power computed)
    if mode == MODE_CAP:
        s.energy_wh   = mv[19:23].cast('f')[0] * 0.001
        s.capacity_ah = mv[23:27].cast('f')[0] * 0.001
        s.setpoint_in_packet = False
    elif mode == MODE_DCR:
        s.dcr_i1   = mv[15:19].cast('f')[0]
        s.dcr_i2   = mv[19:23].cast('f')[0]
        s.dcr_mohm = mv[23:27].cast('f')[0]
        s.runtime  = 0
        s.current  = 0.0
        s.power    = 0.0
        s.setpoint_in_packet = False
    elif mode in (MODE_ADV, MODE_POWER, MODE_DT, MODE_POWER_RPT):
        s.runtime  = 0
        s.setpoint_in_packet = False
    else:
        s.temperature = mv[19:23].cast('f')[0]
        s.setpoint    = mv[23:27].cast('f')[0]
    # Fan speed (0=off..5=max) is split across two bytes:
    # byte5 bits 6-7 -> low 2 bits, byte6 bit 0 -> MSB. Byte5 bit 5 is unused.
    s.fan_speed   = (b5 >> 6) | ((b6 & 0x01) << 2)
    s.load_on     = (b6 & _STATUS_LOAD_BIT) != 0
    s.lock_on     = (b6 & _STATUS_LOCK_BIT) != 0
    s.mode_name   = MODE_NAMES.get(mode, "?%02X" % mode)
    info = MODE_SETPOINT_INFO.get(mode, ("?", 3, "Setpoint"))
    s.setpoint_unit, s.setpoint_decimals, s.setpoint_label = info
    s.valid = True
    return s
