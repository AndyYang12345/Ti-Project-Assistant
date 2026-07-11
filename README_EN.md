# TI Project Assistant

[中文版](README.md)

[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-blue)](https://github.com/AndyYang12345/Ti-Project-Assistant)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MSPM0](https://img.shields.io/badge/chip-MSPM0-red)](https://www.ti.com/microcontrollers-mcus-processors/arm-based-microcontrollers/mspm0/overview.html)
[![Version](https://img.shields.io/badge/version-v0.2.0-informational)](https://github.com/AndyYang12345/Ti-Project-Assistant)

**One command** to bootstrap a complete TI MSPM0 embedded project from a [SysConfig](https://www.ti.com/tool/SYSCONFIG) file. No CCS required.

---

## Installation

```bash
pip install ti-project-assistant
```

Once installed, the `mspm0-init` command is available system-wide (Windows / Linux / macOS).

---

## Quick Start

```bash
# 1. Configure your chip and pins in SysConfig GUI, save .syscfg to an empty dir, then:
mspm0-init

# 2. Build
cmake --build build -j$(nproc)

# 3. Debug (VSCode)
code .
# Press F5 → choose CMSIS-DAP, XDS110, or JLink
```

After modifying config:

```bash
mspm0-init regenerate    # Only generated files are updated. Your src/ code is safe.
```

---

## Features

| Subcommand | Purpose |
|------------|---------|
| (no args) | Auto-detect `.syscfg` in current dir, create project in-place |
| `new` | Create a new project from `.syscfg` |
| `regenerate` | Re-run SysConfig after pin/peripheral changes, **leaving hand-written code untouched** |

The script automates:

- Invokes SysConfig CLI to generate `ti_msp_dl_config.c/h`, linker script
- Dynamically resolves **all 58 MSPM0 chips** from the SDK at runtime (startup files, driverlib, memory layout — all auto-discovered, no hardcoding)
- Creates a layered project directory structure (`config/`, `src/app/`, `src/modules/`, `src/utils/`)
- Generates `CMakeLists.txt` with `file(GLOB_RECURSE)` for automatic source discovery (arm-none-eabi-gcc toolchain)
- Generates `.vscode/` configs (`launch.json` / `tasks.json` / `c_cpp_properties.json`)
- Auto cmake configure + build verification

---

## Dependencies

### Linux

| Dependency | Version | Install |
|-----------|---------|---------|
| Python | ≥ 3.8 | `sudo apt install python3` |
| ARM GCC | 13.x | `sudo apt install gcc-arm-none-eabi` |
| CMake | ≥ 3.13 | `sudo apt install cmake` |
| Ninja | any | `sudo apt install ninja-build` |
| TI MSPM0 SDK | 2.x | [Download](https://www.ti.com/tool/MSPM0-SDK) → extract to `~/ti/` |
| TI SysConfig | 1.x | [Download](https://www.ti.com/tool/SYSCONFIG) → extract to `~/ti/` |
| OpenOCD (TI fork) | 1.3.x | Included with [CCS Theia](https://www.ti.com/tool/CCSTUDIO) |
| arm-none-eabi-gdb | 14.x | Auto-installed from TI VSCode plugin |

One-liner:

```bash
sudo apt install python3 gcc-arm-none-eabi cmake ninja-build
```

### Windows

| Dependency | Version | Install |
|-----------|---------|---------|
| Python | ≥ 3.8 | [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` |
| ARM GCC | 13.x | [arm Developer](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads) → add `bin\` to PATH |
| CMake | ≥ 3.13 | [cmake.org](https://cmake.org/download/) or `winget install Kitware.CMake` |
| Ninja | any | [ninja-build.org](https://ninja-build.org/) or `winget install Ninja-build.Ninja` |
| TI MSPM0 SDK | 2.x | [Download](https://www.ti.com/tool/MSPM0-SDK) → extract to `C:\ti\` |
| TI SysConfig | 1.x | [Download](https://www.ti.com/tool/SYSCONFIG) → extract to `C:\ti\` |
| OpenOCD (TI fork) | 1.3.x | Included with [CCS Theia](https://www.ti.com/tool/CCSTUDIO) |
| arm-none-eabi-gdb | 14.x | Auto-installed from TI VSCode plugin |

---

## Environment Variables

All are **optional**. The tool auto-discovers installations if unset.

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

**Windows** — set in System Environment Variables or PowerShell:

```powershell
$env:MSPM0_SDK = "C:\ti\mspm0_sdk_2_10_00_04"
$env:SYSCONFIG_DIR = "C:\ti\sysconfig_1.27.1"
$env:TI_ROOT = "C:\ti"
```

---

## Usage

### Create a new project

```bash
# Simplest: run in a directory with only a .syscfg file
mspm0-init

# Auto-discover .syscfg in current dir
mspm0-init new -n my_project

# Explicit syscfg file
mspm0-init new myboard.syscfg -n my_project -d xds110

# Without syscfg (bare-metal start)
mspm0-init new --device MSPM0G3507 --package "LQFP-48(PT)" -n bare_start
```

### Regenerate config

```bash
mspm0-init regenerate               # inside project dir
mspm0-init regenerate /path/to/proj # specify path
```

`regenerate` backs up old files to `.sysconfig_backup/`. Use `--no-backup` to skip.

### All options

```
mspm0-init new [syscfg] -n NAME [options]

  -n, --name NAME        Project name (required)
  -o, --output DIR       Output directory (default: ./<name>/)
  -s, --sdk PATH         MSPM0 SDK path
  --sysconfig PATH       SysConfig install dir
  -d, --debugger TYPE    cmsis-dap (default) | xds110 | jlink | none
  --device DEVICE        Specify chip manually, e.g. MSPM0G3507
  --package PACKAGE      Specify package, e.g. LQFP-48(PT)
  --dry-run              Preview only, don't create files
  --no-build             Skip cmake build verification

mspm0-init regenerate [project_dir] [options]

  --no-build             Skip rebuild
  --no-backup            Don't backup old files
  --dry-run              Preview mode
```

---

## Project Structure

```
my_project/
├── CMakeLists.txt              # Build definition
├── my_project.syscfg           # Original SysConfig config
├── config/
│   ├── ti_msp_dl_config.h      # Auto-generated — DO NOT EDIT
│   ├── ti_msp_dl_config.c      # Auto-generated — DO NOT EDIT
│   ├── device_linker.lds       # Linker script
│   └── device.opt              # Compiler options
├── inc/
│   ├── main.h                  # Application header
│   ├── app/                    # Application-layer headers
│   ├── driver/                 # Driver headers
│   ├── modules/                # Module headers
│   └── utils/                  # Utility headers
├── src/
│   ├── main.c                  # Application entry (write code here)
│   ├── app/                    # Application-layer sources
│   ├── driver/                 # Driver sources
│   ├── modules/                # Module sources
│   └── utils/                  # Utility sources
├── lib/                        # Local static libraries
├── excluded/                   # Build-excluded SysConfig artifacts
├── build/                      # Build output (ELF, HEX, BIN, MAP)
└── .vscode/
    ├── launch.json             # Debug config (CMSIS-DAP / XDS110 / JLink)
    ├── tasks.json              # Build tasks
    └── c_cpp_properties.json   # IntelliSense config
```

---

## Supported Chips

**All 58 MSPM0 devices in the SDK work out of the box.** No manual chip entries needed.

The tool discovers chip parameters at runtime by parsing the SDK's `DeviceFamily.h`, scanning startup file directories, reading pre-built linker scripts, and falling back to `macros.tirex.json` — including Flash/SRAM layout, startup files, and driverlib paths.

If your chip is in the TI MSPM0 SDK, `mspm0-init` recognizes it automatically.

Supported families include:

| Family | Example devices |
|--------|----------------|
| MSPM0Gx5xx | G3507, G3519, G3107, G1507, G1519 … |
| MSPM0Gx1xx | G1105, G1106 … |
| MSPM0Lx3xx | L1306, L1345, L2228 … |
| MSPM0Lx2xx | L1227, L2227, L1228 … |
| MSPM0Cx1xx | C1105, C1106 … |
| MSPM0Hx2xx | H3215 … |

[View full SDK device list →](https://www.ti.com/tool/MSPM0-SDK)

---

## Dependency Graph

```
mspm0-init
├── SysConfig 1.x ────────────── Generates ti_msp_dl_config.c/h, linker script
├── MSPM0 SDK 2.x
│   ├── driverlib.a ──────────── Hardware abstraction layer
│   ├── startup_*.c ──────────── Interrupt vector table + startup code
│   ├── CMSIS Core ───────────── Cortex-M0+ register definitions
│   └── DeviceFamily.h ──────── Chip family macros
├── arm-none-eabi-gcc 13.x ──── Cross-compiler
├── CMake + Ninja ───────────── Build system
├── OpenOCD 1.3.x ───────────── GDB Server + flashing
├── arm-none-eabi-gdb 14.x ──── Source-level debug
└── VS Code + Cortex-Debug ──── IDE integration
```

## Development

```bash
git clone git@github.com:AndyYang12345/Ti-Project-Assistant.git
cd ti-project-assistant

# Editable install (recommended, changes take effect immediately)
pip install -e .

# Or manual install to PATH (Linux)
ln -s $(pwd)/mspm0-init ~/bin/mspm0-init

# Or manual install to PATH (Windows)
# Add ti-project-assistant directory to system PATH
```

## License

[MIT](LICENSE)
