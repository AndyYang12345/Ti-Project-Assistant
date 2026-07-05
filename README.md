# TI Project Assistant

[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-blue)](https://github.com/AndyYang12345/Ti-Project-Assistant)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MSPM0](https://img.shields.io/badge/chip-MSPM0-red)](https://www.ti.com/microcontrollers-mcus-processors/arm-based-microcontrollers/mspm0/overview.html)
[![GitHub release](https://img.shields.io/badge/version-v0.1.0-informational)](https://github.com/AndyYang12345/Ti-Project-Assistant)

One-click CLI tool to bootstrap a **TI MSPM0** embedded project from a [SysConfig](https://www.ti.com/tool/SYSCONFIG) graphical configuration file.  
No CCS required — just a `.syscfg`, and you get a fully buildable CMake + ARM GCC project with VSCode debug support.

---

## Features

- **`new`** — create a new project from `.syscfg` (or `--device` for bare-metal)
- **`regenerate`** — re-run SysConfig after modifying pin/peripheral config, keeping hand-written code untouched
- **Auto-discover** SDK & SysConfig installations under `~/ti/` (Linux) or `C:\ti\` (Windows)
- **Auto-discover** `.syscfg` files in the current directory
- Generates: `CMakeLists.txt`, linker script, `main.c`, `main.h`, `.vscode/` configs
- Supports **CMSIS-DAP** and **XDS110** debug probes

---

## Quick Start

```bash
# 1. Create a .syscfg with SysConfig GUI, then:
mspm0-init new -n my_blinky

# 2. Build
cd my_blinky
cmake --build build -j$(nproc)

# 3. Debug (VSCode)
code .
# Press F5 → CMSIS-DAP or XDS110
```

### Modify config later

```bash
# Edit your .syscfg in SysConfig GUI, then:
cd my_blinky
mspm0-init regenerate
# → Only generated files are updated. Your src/ code is safe.
```

---

## Dependencies

### Linux

| Dependency | Version | Install |
|-----------|---------|---------|
| Python | ≥ 3.8 | `sudo apt install python3` |
| ARM GCC Toolchain | 13.x | `sudo apt install gcc-arm-none-eabi` |
| CMake | ≥ 3.13 | `sudo apt install cmake` |
| Ninja | any | `sudo apt install ninja-build` |
| TI MSPM0 SDK | 2.x | [Download](https://www.ti.com/tool/MSPM0-SDK) → extract to `~/ti/` |
| TI SysConfig | 1.x | [Download](https://www.ti.com/tool/SYSCONFIG) → extract to `~/ti/` |
| OpenOCD (TI fork) | 1.3.x | Included with [CCS Theia](https://www.ti.com/tool/CCSTUDIO) or [ti-embedded-debug](https://dev.ti.com/gallery/view/2966040/ti-embedded-debug/) |
| arm-none-eabi-gdb | 14.x | Same as OpenOCD |

**One-liner:**

```bash
sudo apt install python3 gcc-arm-none-eabi cmake ninja-build
```

### Windows

| Dependency | Version | Install |
|-----------|---------|---------|
| Python | ≥ 3.8 | [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` |
| ARM GCC Toolchain | 13.x | [arm Developer](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads) → add `bin\` to PATH |
| CMake | ≥ 3.13 | [cmake.org](https://cmake.org/download/) or `winget install Kitware.CMake` |
| Ninja | any | [ninja-build.org](https://ninja-build.org/) or `winget install Ninja-build.Ninja` |
| TI MSPM0 SDK | 2.x | [Download](https://www.ti.com/tool/MSPM0-SDK) → extract to `C:\ti\` |
| TI SysConfig | 1.x | [Download](https://www.ti.com/tool/SYSCONFIG) → extract to `C:\ti\` |
| OpenOCD (TI fork) | 1.3.x | Included with [CCS Theia](https://www.ti.com/tool/CCSTUDIO) |
| arm-none-eabi-gdb | 14.x | Same as OpenOCD |

---

## Environment Variables

All are **optional**. If unset, the tool auto-discovers installations under the Ti base directory.

| Variable | Linux default | Windows default | Description |
|----------|--------------|-----------------|-------------|
| `MSPM0_SDK` | `~/ti/mspm0_sdk_*` | `C:\ti\mspm0_sdk_*` | MSPM0 SDK root |
| `SYSCONFIG_DIR` | `~/ti/sysconfig_*` | `C:\ti\sysconfig_*` | SysConfig install directory |
| `TI_ROOT` | `~/ti` | `C:\ti` | Base directory for all TI tools |
| `OPENOCD_DIR` | `~/.config/.../openocd/*` | `C:\ti\ccs_base\DebugServer\bin\openocd.exe` | OpenOCD directory or executable |
| `GDB_DIR` | `~/.config/.../gdb/*` | `C:\ti\ccs_base\DebugServer\bin\arm-none-eabi-gdb.exe` | GDB directory |

### Recommended setup

**Linux** — add to `~/.zshrc` or `~/.bashrc`:

```bash
export MSPM0_SDK=~/ti/mspm0_sdk_2_10_00_04
export SYSCONFIG_DIR=~/ti/sysconfig_1.27.1
```

**Windows** — set in System Environment Variables or PowerShell profile:

```powershell
$env:MSPM0_SDK = "C:\ti\mspm0_sdk_2_10_00_04"
$env:SYSCONFIG_DIR = "C:\ti\sysconfig_1.27.1"
$env:TI_ROOT = "C:\ti"
```

---

## Usage

```bash
# ── Create a new project ──

# Auto-discover .syscfg in current dir
mspm0-init new -n my_project

# Explicit syscfg file
mspm0-init new myboard.syscfg -n my_project -d xds110

# Without syscfg (bare-metal start)
mspm0-init new --device MSPM0G3507 --package "LQFP-48(PT)" -n bare_start

# ── Regenerate after config change ──

mspm0-init regenerate               # inside project dir
mspm0-init regenerate /path/to/proj # specify path

# ── Options ──

-o, --output DIR      Output directory (default: ./<name>/)
-s, --sdk PATH        MSPM0 SDK path
--sysconfig PATH      SysConfig install dir
-d, --debugger TYPE   cmsis-dap (default) | xds110 | none
--dry-run             Preview only, don't create files
--no-build            Skip cmake build verification
```

---

## Project Structure

```
my_project/
├── CMakeLists.txt              # Build definition
├── my_project.syscfg           # Original SysConfig config
├── ti_msp_dl_config.h          # Auto-generated — DO NOT EDIT
├── ti_msp_dl_config.c          # Auto-generated — DO NOT EDIT
├── device_linker.lds           # Linker script
├── inc/
│   ├── main.h
│   └── driver/                 # Your driver headers
├── src/
│   ├── main.c                  # Application entry
│   └── driver/                 # Your driver sources
├── lib/                        # Local static libraries
├── excluded/                   # Build-excluded SysConfig artifacts
├── build/                      # Build output (ELF, HEX, BIN, MAP)
└── .vscode/
    ├── launch.json             # Debug config (CMSIS-DAP / XDS110)
    ├── tasks.json              # Build tasks
    └── c_cpp_properties.json   # IntelliSense config
```

---

## Supported Chips

[![MSPM0G3507](https://img.shields.io/badge/MSPM0G3507-128KB%20Flash%20%7C%2032KB%20SRAM-red)](https://www.ti.com/product/MSPM0G3507)
[![MSPM0G3505](https://img.shields.io/badge/MSPM0G3505-64KB%20Flash%20%7C%2016KB%20SRAM-red)](https://www.ti.com/product/MSPM0G3505)
[![MSPM0L1306](https://img.shields.io/badge/MSPM0L1306-64KB%20Flash%20%7C%208KB%20SRAM-red)](https://www.ti.com/product/MSPM0L1306)

Adding a new chip: add an entry to `CHIP_MAP` in the script.

---

## Development

```bash
git clone git@github.com:AndyYang12345/Ti-Project-Assistant.git
cd ti-project-assistant

# install as CLI tool
ln -s $(pwd)/mspm0-init ~/bin/mspm0-init   # Linux
# or add to PATH on Windows

# branches
# main    — stable Linux
# windows — Windows-compatible
```
