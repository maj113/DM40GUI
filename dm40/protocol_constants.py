"""Protocol constants and command maps for DM40."""

CMD_ID = b"\xaf\x05\x03\x08\x00\x41"
CMD_READ = b"\xaf\x05\x03\x09\x00\x40"
HEADER = b"\xdf\x05\x03\x09"

CMD_HOLD_ON = b"\xaf\x05\x03\x04\x01\x01"
CMD_HOLD_OFF = b"\xaf\x05\x03\x04\x01\x00"
CMD_AUTO_ON = b"\xaf\x05\x03\x03\x01\x01"
CMD_AUTO_OFF = b"\xaf\x05\x03\x03\x01\x00"
CMD_RELATIVE = b"\xaf\x05\x03\x05\x01\x01"
CMD_CAP = b"\xaf\x05\x03\x06\x01\x03"
CMD_DIODE = b"\xaf\x05\x03\x06\x01\x04"
CMD_CONT = b"\xaf\x05\x03\x06\x01\x44"
CMD_HZ = b"\xaf\x05\x03\x06\x01\x05"
CMD_TEMP = b"\xaf\x05\x03\x06\x01\x45"


RANGE_CYCLE_GROUPS = (
    (
        "V",
        (
            ("VDC", 0x30),
            ("VAC", 0x70),
            ("VDC+AC", 0xB0),
        ),
    ),
    (
        "A",
        (
            ("ADC", 0x39),
            ("AAC", 0x79),
            ("ADC+AC", 0xB9),
        ),
    ),
    (
        "Ohm",
        (
            ("RES", 0x32),
            ("RES_ONLINE", 0x72),
        ),
    ),
)

COMMAND_CYCLE_GROUPS = (
    (
        "DIODE/CONT",
        (
            ("DIODE", CMD_DIODE),
            ("CONT", CMD_CONT),
        ),
    ),
    (
        "Hz/Temp",
        (
            ("Hz", CMD_HZ),
            ("Temp", CMD_TEMP),
        ),
    ),
)

RANGE_KIND_TO_GROUP = {
    "VDC": "V",
    "VAC": "V",
    "VDC+AC": "V",
    "ADC": "A",
    "AAC": "A",
    "ADC+AC": "A",
    "RES": "Ohm",
    "RES_ONLINE": "Ohm",
}

COMMAND_KIND_TO_GROUP = {
    "DIODE": "DIODE/CONT",
    "CONT": "DIODE/CONT",
    "FREQ": "Hz/Temp",
    "TEMP": "Hz/Temp",
}

COMMAND_KIND_LABELS = {
    "FREQ": "Hz",
    "TEMP": "Temp",
}

TOGGLE_COMMANDS = (
    ("AUTO", CMD_AUTO_ON, CMD_AUTO_OFF),
    ("HOLD", CMD_HOLD_ON, CMD_HOLD_OFF),
    ("CAP", CMD_CAP, None),
)

MOMENTARY_COMMANDS = (
    ("Relative", CMD_RELATIVE),
)

FLAG_INFO = {
    0x00: ("VDC", "600mV"),
    0x08: ("VDC", "6V"),
    0x10: ("VDC", "60V"),
    0x18: ("VDC", "600V"),
    0x20: ("VDC", "1000V"),
    0x28: ("VDC", "AUTO"),
    0x30: ("VDC", "AUTO+"),
    0x40: ("VAC", "600mV"),
    0x48: ("VAC", "6V"),
    0x50: ("VAC", "60V"),
    0x58: ("VAC", "600V"),
    0x60: ("VAC", "1000V"),
    0x68: ("VAC", "AUTO"),
    0x70: ("VAC", "AUTO+"),
    0x80: ("VDC+AC", "600mV"),
    0x88: ("VDC+AC", "6V"),
    0x90: ("VDC+AC", "60V"),
    0x98: ("VDC+AC", "600V"),
    0xA0: ("VDC+AC", "1000V"),
    0xA8: ("VDC+AC", "AUTO"),
    0xB0: ("VDC+AC", "AUTO+"),
    0x01: ("ADC", "600uA"),
    0x09: ("ADC", "6mA"),
    0x11: ("ADC", "60mA"),
    0x19: ("ADC", "600mA"),
    0x21: ("ADC", "6A"),
    0x29: ("ADC", "10A"),
    0x31: ("ADC", "AUTO"),
    0x39: ("ADC", "AUTO+"),
    0x41: ("AAC", "600uA"),
    0x49: ("AAC", "6mA"),
    0x51: ("AAC", "60mA"),
    0x59: ("AAC", "600mA"),
    0x61: ("AAC", "6A"),
    0x69: ("AAC", "10A"),
    0x71: ("AAC", "AUTO"),
    0x79: ("AAC", "AUTO+"),
    0x81: ("ADC+AC", "600uA"),
    0x89: ("ADC+AC", "6mA"),
    0x91: ("ADC+AC", "60mA"),
    0x99: ("ADC+AC", "600mA"),
    0xA1: ("ADC+AC", "6A"),
    0xA9: ("ADC+AC", "10A"),
    0xB1: ("ADC+AC", "AUTO"),
    0xB9: ("ADC+AC", "AUTO+"),
    0x02: ("RES", "600Ω"),
    0x0A: ("RES", "6kΩ"),
    0x12: ("RES", "60kΩ"),
    0x1A: ("RES", "600kΩ"),
    0x22: ("RES", "6MΩ"),
    0x2A: ("RES", "60MΩ"),
    0x32: ("RES", "AUTO"),
    0x42: ("RES_ONLINE", "600Ω"),
    0x4A: ("RES_ONLINE", "6kΩ"),
    0x52: ("RES_ONLINE", "60kΩ"),
    0x5A: ("RES_ONLINE", "600kΩ"),
    0x62: ("RES_ONLINE", "6MΩ"),
    0x6A: ("RES_ONLINE", "60MΩ"),
    0x72: ("RES_ONLINE", "AUTO"),
    0x03: ("CAP", "AUTO"),
    0x04: ("DIODE", "AUTO"),
    0x44: ("CONT", "AUTO"),
    0x05: ("FREQ", "AUTO"),
    0x45: ("TEMP", "AUTO"),
}

# Format: (fs, unit, mul, decimals)
ALT_SCALE_MAP = {
    0x04: (0.6, "mV", 1e3, 2),
    0x08: (6.0, "V", 1.0, 4),
    0x18: (6.0, "V", 1.0, 4),
    0x16: (60.0, "V", 1.0, 3),
    0x14: (600.0, "V", 1.0, 2),
    0x12: (6000.0, "V", 1.0, 1),
}

AMP_SCALE_MAP = {
    0x04: (600e-6, "uA", 1e6, 2),
    0x02: (6000e-6, "uA", 1e6, 1),
    0x16: (60e-3, "mA", 1e3, 3),
    0x14: (600e-3, "mA", 1e3, 2),
    0x28: (6.0, "A", 1.0, 4),
    0x26: (60.0, "A", 1.0, 3),
}

RES_SCALE_MAP = {
    0x04: (600.0, "Ω", 1.0, 2),
    0x02: (6000.0, "Ω", 1.0, 1),
    0x18: (6000.0, "kΩ", 0.001, 4),
    0x16: (60000.0, "kΩ", 0.001, 3),
    0x14: (600000.0, "kΩ", 0.001, 2),
    0x28: (6e6, "MΩ", 1e-6, 4),
    0x26: (6e7, "MΩ", 1e-6, 3),
}

FREQ_SCALE_MAP = {
    0x06: (60.0, "Hz", 1.0, 3),
    0x04: (600.0, "Hz", 1.0, 2),
    0x02: (6_000.0, "Hz", 1.0, 1),
    0x18: (6_000.0, "kHz", 1e-3, 4),
    0x16: (60_000.0, "kHz", 1e-3, 3),
    0x14: (600_000.0, "kHz", 1e-3, 2),
}

CAP_SCALE_MAP = {
    0x06: (6e-9, "nF", 1e9, 3),
    0x04: (60e-9, "nF", 1e9, 2),
    0x02: (600e-9, "nF", 1e9, 1),
    0x16: (6e-6, "uF", 1e6, 3),
    0x14: (60e-6, "uF", 1e6, 2),
    0x12: (600e-6, "uF", 1e6, 1),
    0x26: (6e-3, "mF", 1e3, 3),
    0x24: (60e-3, "mF", 1e3, 2),
}

UNIT_TO_BASE = {
    "mV": 1e-3,
    "V": 1.0,
    "uA": 1e-6,
    "mA": 1e-3,
    "A": 1.0,
    "Ω": 1.0,
    "kΩ": 1e3,
    "MΩ": 1e6,
    "Hz": 1.0,
    "kHz": 1e3,
    "nF": 1e-9,
    "uF": 1e-6,
    "mF": 1e-3,
    "°C": 1.0,
    "°F": 1.0,
    "%": 1.0,
}

MODE_SLOT_MAP = {
    "VDC": ("M1",),
    "VAC": ("M1", "DUTY", "FREQ"),
    "VDC+AC": ("M1", "DC", "AC"),
    "ADC": ("M1",),
    "AAC": ("M1", "DUTY", "FREQ"),
    "ADC+AC": ("M1", "DC", "AC"),
    "RES": ("M1",),
    "RES_ONLINE": ("M1",),
    "CAP": ("M1",),
    "CONT": ("M1",),
    "DIODE": ("M1", "RES"),
    "FREQ": ("FREQ", "DUTY"),
    "TEMP": ("TC", "TF", "TI"),
}
