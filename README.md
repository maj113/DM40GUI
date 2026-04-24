# DM40GUI

[![Build](https://github.com/maj113/DM40GUI/actions/workflows/build.yml/badge.svg)](https://github.com/maj113/DM40GUI/actions/workflows/build.yml)
[![GitHub Release](https://img.shields.io/github/v/release/maj113/DM40GUI)](https://github.com/maj113/DM40GUI/releases/latest)
[![License](https://img.shields.io/github/license/maj113/DM40GUI)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%201703%2B-0078d4)](#requirements)

> A Windows desktop app for **DM40-series multimeters** and **EL15 electronic loads** over Bluetooth Low Energy.
> Tkinter front-end, a custom WinRT BLE transport, and zero third-party Python dependencies at runtime.

<p align="center">
  <img src="docs/screenshots/app-graph-selected.png" alt="DM40GUI waveform view with a range selection" width="918"/>
</p>

> [!TIP]
> Prebuilt binaries are available on the [Releases](https://github.com/maj113/DM40GUI/releases/latest) page.

> [!WARNING]
> Windows only. The transport layer talks to WinRT BLE GATT directly; there is no maintained Linux or macOS port.

## Contents

- [Features](#features)
- [Device Support](#device-support)
- [Requirements](#requirements)
- [Run from Source](#run-from-source)
- [Build for Release](#build-for-release)
- [Keybinds](#keybinds)
- [Architecture](#architecture)
- [Protocol Notes](#protocol-notes)
- [Notes](#notes)
- [License](#license)

## Features

- One binary, two device families: handlers are dispatched dynamically after the device is identified.
- Scrolling waveform with live value, pause/resume, click-to-pin, drag-to-select range with min / max / Δ.
- Raw packet inspector with inline CRC pass/fail tags and integrated find popup.
- One-shot CSV buffer export or continuous CSV recording.
- 17 built-in themes with a live preview browser; selection is persisted across sessions.
- Release build is tuned for small size: Nuitka one-file + size-oriented MSVC flags + aggressive stdlib pruning.

## Device Support

| Device | Status | UI / Telemetry | Controls |
|---|---|---|---|
| DM40 series | Supported | Live reading, waveform, raw packet view, stats | Hold, auto, relative, range and mode switching |
| EL15 | Experimental | Voltage / current / power, waveform, raw packet view, stats | Load on/off, CC / CV / CR / CP / CAP / DCR mode switching, setpoint entry |

<p align="center">
  <img src="docs/screenshots/themes.gif" alt="Built-in theme browser preview" width="918"/>
</p>

### DM40

- Large primary reading with auxiliary values.
- Mode, range, battery, charging, lock, and hold state rendering.
- Hold, auto-range, relative, capacitance, diode / continuity, frequency, and temperature controls.
- Roughly matches `atk-xtool` feature coverage for day-to-day meter use.

### EL15

- Dedicated voltage, current, and power readout cells.
- Runtime, temperature, fan speed, mode, load state, and setpoint display.
- CC, CV, CR, CP, CAP (battery capacity), and DCR (DC resistance) mode switching from the main control bar.
- CAP mode shows accumulated energy (Wh) and capacity (Ah) in place of the setpoint.
- DCR mode shows the I1 / I2 test currents and the measured milliohm resistance.
- Device-only modes (`POW [A]`, `POW [DT]`, `ADV [L]`, `ADV [S]`) surface as a single disabled radio that tracks the active mode; the setpoint entry is disabled in these modes.
- Load control and editable setpoint command entry.

## Requirements

- **Windows 10 version 1703** (Creators Update, build 15063) or newer. The BLE GATT APIs this app relies on (`IBluetoothLEDevice3`, `IGattDeviceService3`) were introduced in that release; `IBluetoothLEDevice6` connection tuning is used when available and skipped otherwise.
- **Python 3.13+** with Tkinter (source runtime only).
- **MSVC Build Tools** compatible with Nuitka `--msvc=latest` (release build only).

> [!NOTE]
> Other Python versions may work, but are currently untested.

## Run from Source

```powershell
py -3.13 main.py
```

No extra package install is required for source execution.

## Build for Release

Install the build dependency:

```powershell
py -3.13 -m pip install --upgrade nuitka
```

Then run:

```powershell
build_release.cmd
```

The release path is intentionally size-focused:

- one-file Nuitka build
- size-oriented compiler and linker flags
- precompiled minimal `ctypes` shim for frozen builds
- aggressive exclusion of unused stdlib modules and Tcl/Tk payloads
- optional module-closure reports for auditing import growth

The build script is CI-friendly:

- deterministic compiler and linker environment setup
- non-zero exit on failure
- configurable via `DM40_*` environment variables

Build environment variables:

| Variable | Purpose |
|---|---|
| `DM40_PYTHON` | Python launcher or command (default: `py -3.13`) |
| `DM40_OUT_DIR` | Build output directory |
| `DM40_CCFLAGS` | Additional compiler flags |
| `DM40_LINKFLAGS` | Additional linker flags |
| `DM40_NUITKA_FLAGS` | Additional Nuitka flags |
| `DM40_MODE_FLAGS` | Build mode flags (default: `--deployment`) |
| `DM40_CONSOLE_MODE` | Nuitka console mode (`disable`, `attach`, `force`) |
| `DM40_MSVC` | Nuitka MSVC selector (default: `latest`) |
| `DM40_JOBS` | Parallel compile jobs |
| `DM40_EMIT_MODULE_REPORTS` | Emit `modules.txt` and XML report (`1` local default, `0` when `CI` is set) |

Minimal CI example:

```cmd
set DM40_PYTHON=py -3.13
set DM40_OUT_DIR=build\ci\nuitka
call build_release.cmd
```

## Keybinds

| Scope | Keybind | Action |
|---|---|---|
| Global | `P` | Pause or resume waveform updates |
| Global | `R` | Start or stop waveform CSV recording |
| Global | `Ctrl+S` | Save the current waveform buffer to CSV |
| Global | `Ctrl+C` | Copy the current reading text |
| Raw packet view | `Ctrl+F` | Open the find popup |
| Raw packet view | `Enter` / `F3` | Next match |
| Raw packet view | `Shift+Enter` / `Shift+F3` | Previous match |
| Raw packet view | `Esc` | Close the find popup or clear its focus |
| Waveform | Left click on trace | Pin a tooltip at a sample |
| Waveform | Left-click drag | Select a range and show min / max / Δ |
| Waveform | Right click | Clear the pinned point or current selection |

## Architecture

| Path | Description |
|---|---|
| `main.py` | Entry point; installs frozen-build shims before launching the app |
| `shared/base_app.py` | Single-window Tk app, scan/connect flow, waveform view, and handler selection |
| `shared/ble_worker.py` | Shared BLE worker plus device-family probe |
| `shared/device_registry.py` | Single-source registry of supported device handlers |
| `shared/nanowinbt/` | Custom Windows BLE and WinRT transport layer |
| `shared/mini_asyncio.py` | Small async runtime used instead of full `asyncio` |
| `dm40/app.py` | DM40 handler, controls, and UI updates |
| `dm40/parsing.py` | DM40 packet parsing and meter-state decoding |
| `dm40/protocol_constants.py` | DM40 commands, flags, scale maps, and mode groups |
| `el15/app.py` | EL15 handler, controls, and UI updates |
| `el15/protocol_constants.py` | EL15 commands and status packet parsing |
| `GUI/` | Shared widgets, controls, theming, and custom dialogs |
| `build_release.cmd` | One-file Nuitka build script |

## Protocol Notes

Reverse-engineered from BLE HCI captures and device traffic inspection.

### Shared BLE Endpoints

Both device families currently use the same BLE service and characteristic layout in the shared worker:

| Direction | UUID |
|---|---|
| Service | `0000fff0-0000-1000-8000-00805f9b34fb` |
| Notify | `0000fff1-0000-1000-8000-00805f9b34fb` |
| Write | `0000fff3-0000-1000-8000-00805f9b34fb` |

### DM40 Protocol

DM40 command frames are 6 bytes:

```text
AF 05 03 <cmd> <arg> <checksum>
```

Checksum formula:

```text
(-sum(first_5_bytes)) & 0xFF
```

Common commands:

```text
CMD_ID          af 05 03 08 00 41
CMD_READ        af 05 03 09 00 40
CMD_HOLD_ON     af 05 03 04 01 01
CMD_HOLD_OFF    af 05 03 04 01 00
CMD_AUTO_ON     af 05 03 03 01 01
CMD_AUTO_OFF    af 05 03 03 01 00
CMD_RELATIVE    af 05 03 05 01 01
CMD_CAP         af 05 03 06 01 03
CMD_DIODE       af 05 03 06 01 04
CMD_CONT        af 05 03 06 01 44
CMD_HZ          af 05 03 06 01 05
CMD_TEMP        af 05 03 06 01 45
```

DM40 notifications use two main packet families:

- Model ID: prefix `DF 05 03 08 14`
- Measurement: prefix `DF 05 03 09`

DM40 measurement decode summary:

| Byte(s) | Field |
|---|---|
| `data[5]` | Mode and range flag (`FLAG_INFO`) |
| `data[6]` | Status byte |
| `data[14:16]` | Primary counts (`m1`, little-endian) |
| `data[12:14]` | Secondary counts (`m2`, little-endian) |
| `data[10:12]` | Tertiary counts (`m3`, little-endian) |
| `data[-8]` | Scale and sign slot 1 |
| `data[-9]` | Scale and sign slot 2 |
| `data[-10]` | Scale and sign slot 3 |

CRC check:

```text
(sum(all_bytes) & 0xFF) == 0
```

DM40 status byte (`data[6]`) summary:

| Bits | Meaning |
|---|---|
| `& 0x07` | Battery level (0-5 bars) |
| `& 0x08` | Charging |
| `& 0x40` | Screen lock |
| `& 0x80` | Hold |

### EL15 Protocol

EL15 status notifications use header:

```text
DF 07 03 08
```

EL15 poll command:

```text
AF 07 03 08 00 3F
```

Common EL15 commands:

```text
CMD_LOAD_ON     af 07 03 09 01 04
CMD_LOAD_OFF    af 07 03 09 01 00
```

Mode switch commands share a common prefix `AF 07 03 03 01 <mode>`:

| Mode | ID | Command |
|---|---|---|
| CC | `0x01` | `af 07 03 03 01 01` |
| CAP | `0x02` | `af 07 03 03 01 02` |
| CV | `0x09` | `af 07 03 03 01 09` |
| DCR | `0x0A` | `af 07 03 03 01 0a` |
| CR | `0x11` | `af 07 03 03 01 11` |
| CP | `0x19` | `af 07 03 03 01 19` |

Device-only modes observed in status packets, cannot be set from the app

| Mode | ID | Label |
|---|---|---|
| Power dynamic test | `0x03` | `POW [DT]` |
| Advanced list | `0x04` | `ADV [L]` |
| Power (auto) | `0x0B` | `POW [A]` |
| Advanced scan | `0x0C` | `ADV [S]` |

Setpoint command layout:

```text
AF 07 03 04 04 <float32 payload>
```

The EL15 parser treats valid status packets as 28-byte frames. The fixed fields are:

| Byte(s) | Field |
|---|---|
| `data[5] & 0x1F` | Mode ID (`ready` bit folded in for CC/CV/CR/CP) |
| `data[5] & 0x01` | Ready / measuring flag (clear while in device menus) |
| `(data[5] >> 6) \| ((data[6] & 0x01) << 2)` | Fan speed (0-5) |
| `data[6] & 0x02` | Load on |
| `data[6] & 0x04` | Panel lock |
| `data[7:11]` | Voltage (`float32`) |
| `data[11:15]` | Current (`float32`, unused in DCR/ADV/POW) |

Bytes `[15:19]`, `[19:23]`, `[23:27]` are mode-specific:

| Mode | `[15:19]` | `[19:23]` | `[23:27]` |
|---|---|---|---|
| CC / CV / CR / CP | Runtime (`int32`, s) | Temperature (`float32`, °C) | Setpoint (`float32`) |
| CAP | Runtime (`int32`, s) | Energy (`float32`, mWh) | Capacity (`float32`, mAh) |
| DCR | I1 (`float32`, A) | I2 (`float32`, A) | Resistance (`float32`, mΩ) |
| ADV [L] / ADV [S] / POW [A] / POW [DT] | unused | unused | unused |

Derived values shown in the UI:

- Power is computed as `voltage * current`
- CAP / DCR reuse the setpoint info row to show energy/capacity or I1/I2/R respectively
- Mode label is resolved from the mode byte via `MODE_NAMES`
- Setpoint unit and precision depend on the active EL15 mode

## Notes

> [!WARNING]
> This project is still in an early reverse-engineering stage. DM40 scale and range coverage is incomplete, and unknown packet variants can still surface as missing flag support.

> [!NOTE]
> If the app crashes with a DM40 `KeyError` during parsing, that usually means a scale or range flag has not been mapped yet. Please report it with the raw packet if possible.

> [!NOTE]
> This project is not affiliated with, endorsed by, or associated with Alientek or any of its subsidiaries.

## License

Licensed under [LICENSE](LICENSE).
