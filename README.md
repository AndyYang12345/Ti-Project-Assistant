# TI Project Assistant（TI 项目助手）

[English version](README_EN.md)

[![Platform](https://img.shields.io/badge/平台-Linux%20%7C%20Windows-blue)](https://github.com/AndyYang12345/Ti-Project-Assistant)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MSPM0](https://img.shields.io/badge/芯片-MSPM0-red)](https://www.ti.com/microcontrollers-mcus-processors/arm-based-microcontrollers/mspm0/overview.html)
[![PyPI](https://img.shields.io/pypi/v/ti-project-assistant?label=版本)](https://pypi.org/project/ti-project-assistant/)

**一行命令**，从 [SysConfig](https://www.ti.com/tool/SYSCONFIG) 图形化配置出发，自动生成完整的 TI MSPM0 嵌入式项目。告别 CCS 手动配置。

---

## 安装

```bash
pip install ti-project-assistant
```

安装完成后，`mspm0-init` 命令即可在终端中使用（Windows / Linux / macOS）。

验证安装：

```bash
mspm0-init --version     # 或 -V，输出版本号确认安装成功
```

---

## 快速开始

```bash
# 1. 用 SysConfig GUI 配好芯片和引脚，保存 .syscfg 到空目录，然后：
mspm0-init

# 2. 构建
cmake --build build -j$(nproc)

# 3. 调试（VSCode）
code .
# 按 F5 → 选择 CMSIS-DAP / XDS110 / JLink
```

修改配置后：

```bash
mspm0-init regenerate    # 仅更新生成文件，src/ 下手写代码安全无虞
```

---

## 功能

| 子命令 | 用途 |
|--------|------|
| （无参数） | 自动发现当前目录 `.syscfg`，原地创建项目 |
| `new` | 从 `.syscfg` 创建新项目 |
| `regenerate` | 修改引脚/外设配置后重新生成代码，**不改动手写代码** |
| `check` | 自检开发环境：arm-gcc、CMake、SysConfig、SDK、OpenOCD 等工具链状态 |
| `--version` / `-V` | 显示当前版本号，用于验证安装 |

脚本自动完成：

- 调用 SysConfig CLI 生成 `ti_msp_dl_config.c/h`、链接脚本
- 动态解析 SDK，自动匹配 **全部 58 款 MSPM0** 芯片的启动文件、driverlib、内存布局（无需硬编码）
- 创建标准分层项目目录结构（`config/`、`src/app/`、`src/modules/`、`src/utils/`）
- 生成 `CMakeLists.txt`（`file(GLOB_RECURSE)` 递归链接，arm-none-eabi-gcc 工具链）
- 生成 `.vscode/` 全套配置（`launch.json` / `tasks.json` / `settings.json` / `c_cpp_properties.json`）
- 内置 `⚙️ 打开 TI SysConfig` VSCode 任务，一键启动图形化配置
- 支持 [Task Buttons](https://marketplace.visualstudio.com/items?itemName=spencerwmiles.vscode-task-buttons) 插件，状态栏直接点击 SysConfig / Build / Clean
- 支持 **4 种调试器**：CMSIS-DAP、XDS110、JLink（原生 Segger GDB Server）、无调试器
- **跨平台工具自动发现**：可执行工具优先从 PATH 读取（Windows/Linux/macOS 一致），环境变量作为回退
- 自动 cmake configure + build 验证
- 自动 `git init` + 写入 `.gitignore`（检测到 Git 已安装时启用，可用 `--no-git` 跳过）

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
| OpenOCD (TI 定制) | 1.3.x | 从 PATH 自动发现，或 TI VSCode 插件自动安装 |
| arm-none-eabi-gdb | 14.x | 从 PATH 自动发现，或 `apt install gdb-multiarch`，或 TI VSCode 插件 |
| JLink (可选) | 7.x+ | [SEGGER 官网](https://www.segger.com/downloads/jlink/) → 安装后自动加入 PATH |

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
| OpenOCD (TI 定制) | 1.3.x | 从 PATH 自动发现，或 TI VSCode 插件自动安装 |
| arm-none-eabi-gdb | 14.x | 从 PATH 自动发现，或 TI VSCode 插件自动安装 |
| JLink (可选) | 7.x+ | [SEGGER 官网](https://www.segger.com/downloads/jlink/) → 安装后自动加入 PATH |

---

## 环境变量

**全部可选**。不设置时脚本从 PATH 自动发现可执行工具，或搜索 TI 工具目录。

| 变量 | Linux 默认值 | Windows 默认值 | 说明 |
|------|-------------|---------------|------|
| `MSPM0_SDK` | `~/ti/mspm0_sdk_*` | `C:\ti\mspm0_sdk_*` | MSPM0 SDK 根目录 |
| `SYSCONFIG_DIR` | `~/ti/sysconfig_*` | `C:\ti\sysconfig_*` | SysConfig 安装目录 |
| `TI_ROOT` | `~/ti` | `C:\ti` | 所有 TI 工具的根目录 |
| `OPENOCD_DIR` | PATH → `~/.config/.../openocd/*` | PATH → `C:\ti\ccs_base\...\openocd.exe` | OpenOCD 目录（PATH 优先，此处为回退） |
| `GDB_DIR` | PATH → `~/.config/.../gdb/*` | PATH → `C:\ti\ccs_base\...\arm-none-eabi-gdb.exe` | GDB 目录（PATH 优先，此处为回退） |
| `JLINK_DIR` | PATH → `/opt/SEGGER/JLink*` | PATH → `C:\Program Files\SEGGER\JLink` | JLink 安装目录（PATH 优先，此处为回退） |

### 工具解析优先级（所有可执行工具统一）

```
1. CLI 参数           (--openocd / --gdb / --jlink-path)    ← 显式指定
2. 环境变量           (OPENOCD_DIR / GDB_DIR / JLINK_DIR)    ← 手动配置
3. PATH               (shutil.which)                         ← 跨平台自动发现
4. TI 插件缓存 / 平台特定路径                                ← 兜底扫描
5. 历史遗留路径       (TI_ROOT / CCS_BASE)                   ← 最后手段
```

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
# 最简单：在只有 .syscfg 的目录下直接运行
mspm0-init

# 自动发现当前目录的 .syscfg
mspm0-init new -n my_project

# 手动指定 syscfg 文件
mspm0-init new myboard.syscfg -n my_project -d xds110

# 无 syscfg，纯裸机起点
mspm0-init new --device MSPM0G3507 --package "LQFP-48(PT)" -n bare_start

# 跳过 Git 初始化
mspm0-init new -n my_project --no-git
```

### 重新生成配置

```bash
mspm0-init regenerate               # 在项目目录内执行
mspm0-init regenerate /path/to/proj # 指定项目路径
```

`regenerate` 会备份旧文件到 `.sysconfig_backup/`，可通过 `--no-backup` 跳过。

更换调试器无需重建项目：
```bash
mspm0-init regenerate -d xds110        # 从 CMSIS-DAP 切换到 XDS110
mspm0-init regenerate -d jlink          # 切换到 JLink（原生 Segger GDB Server）
```

### 全部参数

```
mspm0-init new [syscfg] -n NAME [选项]

  -n, --name NAME        项目名称（必填）
  -o, --output DIR       输出目录（默认 ./<name>/）
  -s, --sdk PATH         MSPM0 SDK 路径
  --sysconfig PATH       SysConfig 安装目录
  -d, --debugger TYPE    cmsis-dap（默认）| xds110 | jlink | none
  --jlink-path PATH      JLink 安装路径（可选，PATH 优先）
  --device DEVICE        手动指定芯片，如 MSPM0G3507
  --package PACKAGE      手动指定封装，如 LQFP-48(PT)
  --dry-run              预览模式，不创建文件
  --no-build             跳过 cmake 构建验证
  --no-git               禁用 Git 自动初始化

mspm0-init regenerate [项目目录] [选项]

  -d, --debugger TYPE    更换调试器：cmsis-dap | xds110 | jlink | none
  --jlink-path PATH      JLink 安装路径（可选，PATH 优先）
  --no-build             跳过重编译
  --no-backup            不备份旧文件
  --dry-run              预览模式
  --no-git               禁用 Git 自动初始化

通用选项:

  --version, -V           显示版本号并退出
  --check                 自检开发环境
  -h, --help              显示完整帮助
```

---

## 生成的项目结构

```
my_project/
├── CMakeLists.txt              # CMake 构建定义
├── .gitignore                  # Git 忽略规则（自动生成）
├── my_project.syscfg           # 原始 SysConfig 配置
├── config/
│   ├── ti_msp_dl_config.h      # 自动生成 — 请勿手动编辑
│   ├── ti_msp_dl_config.c      # 自动生成 — 请勿手动编辑
│   ├── device_linker.lds       # 链接脚本
│   └── device.opt              # 编译选项
├── inc/
│   ├── main.h                  # 应用头文件
│   ├── app/                    # 应用层头文件
│   ├── driver/                 # 驱动头文件
│   ├── modules/                # 功能模块头文件
│   └── utils/                  # 工具头文件
├── src/
│   ├── main.c                  # 应用入口（在此写代码）
│   ├── app/                    # 应用层实现
│   ├── driver/                 # 驱动实现
│   ├── modules/                # 功能模块实现
│   └── utils/                  # 工具实现
├── lib/                        # 本地静态库
├── excluded/                   # 不参与编译的 SysConfig 产物
├── build/                      # 构建输出（ELF / HEX / BIN / MAP）
└── .vscode/
    ├── launch.json             # 调试配置（CMSIS-DAP / XDS110 / JLink）
    ├── tasks.json              # 构建任务 + 打开 SysConfig
    ├── settings.json           # Task Buttons 状态栏按钮
    └── c_cpp_properties.json   # IntelliSense 配置
```

---

## 支持的芯片

**SDK 中的全部 58 款 MSPM0 芯片开箱即用。** 无需手动添加芯片型号。

工具通过运行时解析 SDK 的 `DeviceFamily.h`、启动文件目录、预编译链接脚本和 `macros.tirex.json` 自动发现芯片参数，包括 Flash/SRAM 布局、启动文件、driverlib 路径等。

只要 TI MSPM0 SDK 支持的芯片，`mspm0-init` 就能自动识别。

支持的系列包括：

| 系列 | 代表型号 |
|------|---------|
| MSPM0Gx5xx | G3507, G3519, G3107, G1507, G1519 … |
| MSPM0Gx1xx | G1105, G1106 … |
| MSPM0Lx3xx | L1306, L1345, L2228 … |
| MSPM0Lx2xx | L1227, L2227, L1228 … |
| MSPM0Cx1xx | C1105, C1106 … |
| MSPM0Hx2xx | H3215 … |

[查看 SDK 完整设备列表 →](https://www.ti.com/tool/MSPM0-SDK)

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
├── OpenOCD 1.3.x (可选) ────── GDB Server + 烧录（cmsis-dap / xds110 必装）
├── JLink 7.x+ ──────────────── 原生 GDB Server + 烧录（jlink 模式，推荐 ≥ 7.70）
├── arm-none-eabi-gdb 14.x ──── 源码级调试
├── Git ──────────────────────── 版本控制（自动初始化）
└── VS Code + Cortex-Debug ──── IDE 集成
```

## 开发

```bash
git clone git@github.com:AndyYang12345/Ti-Project-Assistant.git
cd ti-project-assistant

# 可编辑安装（推荐，修改即时生效）
pip install -e .
```

版本号由 `git tag` 驱动（[hatch-vcs](https://github.com/ofek/hatch-vcs)），无需手动修改源文件。构建时自动从 tag 提取版本。

### 发布流程

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
```

推送 tag 后 [GitHub Actions](https://github.com/AndyYang12345/Ti-Project-Assistant/actions/workflows/publish.yml) 自动构建 wheel 并发布到 [PyPI](https://pypi.org/project/ti-project-assistant/)。无需手动运行 build 或 twine。

## 许可证

[MIT](LICENSE)
