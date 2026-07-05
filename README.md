# TI Project Assistant（TI 项目助手）

[English version](README_EN.md)

[![Platform](https://img.shields.io/badge/平台-Linux%20%7C%20Windows-blue)](https://github.com/AndyYang12345/Ti-Project-Assistant)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MSPM0](https://img.shields.io/badge/芯片-MSPM0-red)](https://www.ti.com/microcontrollers-mcus-processors/arm-based-microcontrollers/mspm0/overview.html)
[![Version](https://img.shields.io/badge/版本-v0.1.0-informational)](https://github.com/AndyYang12345/Ti-Project-Assistant)
[![GitHub stars](https://img.shields.io/github/stars/AndyYang12345/Ti-Project-Assistant?style=social)](https://github.com/AndyYang12345/Ti-Project-Assistant)

**一行命令**，从 [SysConfig](https://www.ti.com/tool/SYSCONFIG) 图形化配置出发，自动生成完整的 TI MSPM0 嵌入式项目。

告别 CCS 手动配置 — 你只需用 SysConfig 配好芯片和引脚，剩下的交给脚本。

---

## 功能概览

| 子命令 | 用途 |
|--------|------|
| `new` | 从 `.syscfg` 创建新项目（自动发现当前目录的配置文件） |
| `regenerate` | 修改引脚/外设配置后重新生成代码，**不改动手写代码** |

脚本自动完成：

- 调用 SysConfig CLI 生成 `ti_msp_dl_config.c/h`、链接脚本
- 解析芯片型号，自动映射 SDK 中的启动文件、driverlib 库
- 创建标准项目目录结构
- 生成 `CMakeLists.txt`（arm-none-eabi-gcc 工具链）
- 生成 `.vscode/` 三件套（`launch.json` / `tasks.json` / `c_cpp_properties.json`）
- 自动 cmake configure + build 验证

---

## 快速开始

```bash
# 1. 用 SysConfig GUI 配好芯片和引脚，保存为 .syscfg，然后：
mspm0-init new -n my_blinky

# 2. 构建
cd my_blinky
cmake --build build -j$(nproc)

# 3. 调试（VSCode）
code .
# 按 F5 → 选择 CMSIS-DAP 或 XDS110
```

### 修改配置后

```bash
# 在 SysConfig GUI 中修改 .syscfg，保存，然后：
cd my_blinky
mspm0-init regenerate
# → 仅更新生成文件，src/ 下手写代码安全无虞
```

---

## 依赖安装

### Linux

| 依赖 | 版本 | 安装方式 |
|------|------|----------|
| Python | ≥ 3.8 | 系统自带，或 `sudo apt install python3` |
| ARM GCC | 13.x | `sudo apt install gcc-arm-none-eabi` |
| CMake | ≥ 3.13 | `sudo apt install cmake` |
| Ninja | 任意 | `sudo apt install ninja-build` |
| TI MSPM0 SDK | 2.x | [下载](https://www.ti.com/tool/MSPM0-SDK) → 解压到 `~/ti/` |
| TI SysConfig | 1.x | [下载](https://www.ti.com/tool/SYSCONFIG) → 解压到 `~/ti/` |
| OpenOCD (TI 定制) | 1.3.x | 随 [CCS Theia](https://www.ti.com/tool/CCSTUDIO) 安装 |
| arm-none-eabi-gdb | 14.x | 随 OpenOCD 一起安装 |

一行装完基础工具：

```bash
sudo apt install python3 gcc-arm-none-eabi cmake ninja-build
```

### Windows

| 依赖 | 版本 | 安装方式 |
|------|------|----------|
| Python | ≥ 3.8 | [python.org](https://www.python.org/downloads/) 或 `winget install Python.Python.3.12` |
| ARM GCC | 13.x | [ARM 官网](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads) → 把 `bin\` 加入 PATH |
| CMake | ≥ 3.13 | [cmake.org](https://cmake.org/download/) 或 `winget install Kitware.CMake` |
| Ninja | 任意 | [ninja-build.org](https://ninja-build.org/) 或 `winget install Ninja-build.Ninja` |
| TI MSPM0 SDK | 2.x | [下载](https://www.ti.com/tool/MSPM0-SDK) → 解压到 `C:\ti\` |
| TI SysConfig | 1.x | [下载](https://www.ti.com/tool/SYSCONFIG) → 解压到 `C:\ti\` |
| OpenOCD (TI 定制) | 1.3.x | 随 [CCS Theia](https://www.ti.com/tool/CCSTUDIO) 安装 |
| arm-none-eabi-gdb | 14.x | 随 OpenOCD 一起安装 |

---

## 环境变量

**全部可选**。如果不设置，脚本会自动在 TI 工具目录下搜索。

| 变量 | Linux 默认值 | Windows 默认值 | 说明 |
|------|-------------|---------------|------|
| `MSPM0_SDK` | `~/ti/mspm0_sdk_*` | `C:\ti\mspm0_sdk_*` | MSPM0 SDK 根目录 |
| `SYSCONFIG_DIR` | `~/ti/sysconfig_*` | `C:\ti\sysconfig_*` | SysConfig 安装目录 |
| `TI_ROOT` | `~/ti` | `C:\ti` | 所有 TI 工具的根目录 |
| `OPENOCD_DIR` | `~/.config/.../openocd/*` | `C:\ti\ccs_base\DebugServer\bin\openocd.exe` | OpenOCD 目录或可执行文件 |
| `GDB_DIR` | `~/.config/.../gdb/*` | `C:\ti\ccs_base\DebugServer\bin\arm-none-eabi-gdb.exe` | GDB 目录 |

### 推荐配置

**Linux** — 加入 `~/.zshrc` 或 `~/.bashrc`：

```bash
export MSPM0_SDK=~/ti/mspm0_sdk_2_10_00_04
export SYSCONFIG_DIR=~/ti/sysconfig_1.27.1
```

**Windows** — 在系统环境变量或 PowerShell 中设置：

```powershell
$env:MSPM0_SDK = "C:\ti\mspm0_sdk_2_10_00_04"
$env:SYSCONFIG_DIR = "C:\ti\sysconfig_1.27.1"
$env:TI_ROOT = "C:\ti"
```

---

## 使用详解

### 创建新项目

```bash
# 自动发现当前目录的 .syscfg（最常用）
mspm0-init new -n my_project

# 手动指定 syscfg 文件
mspm0-init new myboard.syscfg -n my_project -d xds110

# 无 syscfg，纯裸机起点
mspm0-init new --device MSPM0G3507 --package "LQFP-48(PT)" -n bare_start
```

### 重新生成配置

```bash
mspm0-init regenerate               # 在项目目录内执行
mspm0-init regenerate /path/to/proj # 指定项目路径
```

`regenerate` 会备份旧文件到 `.sysconfig_backup/`，可通过 `--no-backup` 跳过。

### 全部参数

```
mspm0-init new [syscfg] -n NAME [选项]

  -n, --name NAME        项目名称（必填）
  -o, --output DIR       输出目录（默认 ./<name>/）
  -s, --sdk PATH         MSPM0 SDK 路径
  --sysconfig PATH       SysConfig 安装目录
  -d, --debugger TYPE    cmsis-dap（默认）| xds110 | none
  --device DEVICE        手动指定芯片，如 MSPM0G3507
  --package PACKAGE      手动指定封装，如 LQFP-48(PT)
  --dry-run              预览模式，不创建文件
  --no-build             跳过 cmake 构建验证

mspm0-init regenerate [项目目录] [选项]

  --no-build             跳过重编译
  --no-backup            不备份旧文件
  --dry-run              预览模式
```

---

## 生成的项目结构

```
my_project/
├── CMakeLists.txt              # CMake 构建定义
├── my_project.syscfg           # 原始 SysConfig 配置
├── ti_msp_dl_config.h          # 自动生成 — 请勿手动编辑
├── ti_msp_dl_config.c          # 自动生成 — 请勿手动编辑
├── device_linker.lds           # 链接脚本
├── inc/
│   ├── main.h
│   └── driver/                 # 你的驱动头文件
├── src/
│   ├── main.c                  # 应用入口
│   └── driver/                 # 你的驱动实现
├── lib/                        # 本地静态库
├── excluded/                   # 不参与编译的 SysConfig 产物
├── build/                      # 构建输出（ELF / HEX / BIN / MAP）
└── .vscode/
    ├── launch.json             # 调试配置（CMSIS-DAP / XDS110）
    ├── tasks.json              # 构建任务
    └── c_cpp_properties.json   # IntelliSense 配置
```

---

## 支持的芯片

[![MSPM0G3507](https://img.shields.io/badge/MSPM0G3507-128KB%20Flash%20%7C%2032KB%20SRAM-red)](https://www.ti.com/product/MSPM0G3507)
[![MSPM0G3505](https://img.shields.io/badge/MSPM0G3505-64KB%20Flash%20%7C%2016KB%20SRAM-red)](https://www.ti.com/product/MSPM0G3505)
[![MSPM0L1306](https://img.shields.io/badge/MSPM0L1306-64KB%20Flash%20%7C%208KB%20SRAM-red)](https://www.ti.com/product/MSPM0L1306)

在脚本的 `CHIP_MAP` 字典中添加新条目即可支持更多芯片。

---

## 依赖关系

```
mspm0-init
├── SysConfig 1.x ────────────── 生成 ti_msp_dl_config.c/h、linker script
├── MSPM0 SDK 2.x
│   ├── driverlib.a ──────────── 硬件抽象层
│   ├── startup_*.c ──────────── 中断向量表 + 启动代码
│   ├── CMSIS Core ───────────── Cortex-M0+ 寄存器定义
│   └── DeviceFamily.h ──────── 芯片系列宏
├── arm-none-eabi-gcc 13.x ──── 交叉编译
├── CMake + Ninja ───────────── 构建系统
├── OpenOCD 1.3.x ───────────── GDB Server + 烧录
├── arm-none-eabi-gdb 14.x ──── 源码级调试
└── VS Code + Cortex-Debug ──── IDE 集成
```

## 开发

```bash
git clone git@github.com:AndyYang12345/Ti-Project-Assistant.git
cd ti-project-assistant

# 安装到 PATH（Linux）
ln -s $(pwd)/mspm0-init ~/bin/mspm0-init

# 安装到 PATH（Windows）
# 将 ti-project-assistant 目录加入系统 PATH
```
