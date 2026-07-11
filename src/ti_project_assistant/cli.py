"""
mspm0-init — TI MSPM0 one-click project init tool

Starting from a SysConfig (.syscfg) graphical config file, automates:
  1. Invoke SysConfig CLI to generate ti_msp_dl_config.c/h, linker scripts, etc.
  2. Parse generated headers to extract chip model, pin definitions, clock freq
  3. Auto-map SDK resources (startup file, driverlib, memory layout) from chip model
  4. Create standard project directory structure
  5. Generate CMakeLists.txt (arm-none-eabi-gcc toolchain)
  6. Generate .vscode/ config files (launch.json / tasks.json / c_cpp_properties.json)
  7. Optional: auto-run cmake configure + build to verify

Usage:
  mspm0-init myboard.syscfg -n blinky
  mspm0-init myboard.syscfg -n uart_echo -d xds110 -o ~/projects/uart_echo
  mspm0-init --device MSPM0G3507 --package "LQFP-48(PT)" -n bare_project  # no syscfg needed

Dependencies:
  - Python 3.8+
  - arm-none-eabi-gcc (in PATH)
  - TI SysConfig CLI (SYSconfig_DIR env var or default path)
  - TI MSPM0 SDK   (MSPM0_SDK env var or default path)
"""

import argparse
import os
import re
import sys
import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# =============================================================================
# Platform abstraction — all OS-specific defaults live here
# =============================================================================
IS_WIN = sys.platform == "win32"

# Ti tools base directory
if IS_WIN:
    _TI_BASE = os.environ.get("TI_ROOT", "C:\\ti")
else:
    _TI_BASE = os.environ.get("TI_ROOT", os.path.expanduser("~/ti"))

# SysConfig CLI entry point
_SYSCONFIG_CLI_NAME = "sysconfig_cli.bat" if IS_WIN else "sysconfig_cli.sh"
_SYSCONFIG_GUI_NAME = "sysconfig_gui.bat" if IS_WIN else "sysconfig_gui.sh"
_SYSCONFIG_NW_NAME = "nw.exe" if IS_WIN else "nw"

# CMake generator
_CMAKE_GENERATOR = "Ninja" if IS_WIN else "Unix Makefiles"


def _discover_dir(base: str, pattern: str) -> Optional[str]:
    """Scan <base> for directories matching <pattern>. Return first (sorted) match."""
    if not os.path.isdir(base):
        return None
    candidates = sorted(
        [d for d in os.listdir(base) if re.match(pattern, d)],
        reverse=True,  # latest version first
    )
    return os.path.join(base, candidates[0]) if candidates else None


def _discover_file(base: str, filename: str) -> Optional[str]:
    """Scan <base> recursively for a file named <filename>. Return the first match."""
    if not base or not os.path.isdir(base):
        return None
    for root, _, files in os.walk(base):
        if filename in files:
            return os.path.join(root, filename)
    return None


def _tool_cache_roots() -> List[str]:
    """Return TI debug cache roots that should be searched before other locations."""
    home = Path.home()
    roots: List[str] = []

    if IS_WIN:
        roots.extend([
            str(home / "AppData" / "Local" / "Texas Instruments" / "ti-embedded-debug"),
        ])
    else:
        roots.append(str(home / ".config" / "Texas Instruments" / "ti-embedded-debug"))

    return roots


def _resolve_sdk() -> str:
    """Resolve MSPM0 SDK path: env var > auto-discover > hardcoded default."""
    env = os.environ.get("MSPM0_SDK")
    if env and os.path.isdir(os.path.join(env, ".metadata")):
        return env
    discovered = _discover_dir(_TI_BASE, r"mspm0_sdk_\d+.*")
    if discovered:
        return discovered
    return os.path.join(_TI_BASE, "mspm0_sdk_2_10_00_04")


def _resolve_sysconfig() -> str:
    """Resolve SysConfig path: env var > auto-discover > hardcoded default."""
    env = os.environ.get("SYSCONFIG_DIR")
    if env and os.path.isfile(os.path.join(env, _SYSCONFIG_CLI_NAME)):
        return env
    discovered = _discover_dir(_TI_BASE, r"sysconfig_\d+.*")
    if discovered:
        return discovered
    return os.path.join(_TI_BASE, "sysconfig_1.27.1")


def _read_text_file(path: str) -> str:
    """Read a text file using UTF-8 first, then Windows-compatible fallbacks."""
    # utf-8-sig handles BOM; gbk/cp936 cover Windows Chinese locale
    for encoding in ("utf-8-sig", "gbk", "cp936"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


DEFAULT_SDK_DIR = _resolve_sdk()
DEFAULT_SYSCONFIG_DIR = _resolve_sysconfig()


def _candidate_tool_path(path: Optional[str], executable_name: str) -> Optional[str]:
    """Resolve a user-supplied tool path that may point at a file or directory."""
    if not path:
        return None

    candidate = Path(path)
    if candidate.is_file():
        return str(candidate)
    if candidate.is_dir():
        nested = candidate / executable_name
        if nested.is_file():
            return str(nested)
    return None


def _resolve_openocd_exe(preferred: Optional[str] = None) -> str:
    """Resolve OpenOCD executable path, preferring the TI cache root first."""
    executable_name = "openocd.exe" if IS_WIN else "openocd"

    manual = _candidate_tool_path(preferred, executable_name)
    if manual:
        return manual

    for root in _tool_cache_roots():
        discovered = _discover_file(root, executable_name)
        if discovered:
            return discovered

    env_path = _candidate_tool_path(os.environ.get("OPENOCD_DIR"), executable_name)
    if env_path:
        return env_path

    path_exe = shutil.which(executable_name)
    if path_exe:
        return path_exe

    for root in filter(None, [os.environ.get("TI_ROOT"), os.environ.get("CCS_BASE")]):
        discovered = _discover_file(root, executable_name)
        if discovered:
            return discovered

    return executable_name


def _resolve_gdb_exe(preferred: Optional[str] = None) -> str:
    """Resolve arm-none-eabi-gdb executable path, preferring the TI cache root first."""
    executable_name = "arm-none-eabi-gdb.exe" if IS_WIN else "arm-none-eabi-gdb"

    manual = _candidate_tool_path(preferred, executable_name)
    if manual:
        return manual

    for root in _tool_cache_roots():
        discovered = _discover_file(root, executable_name)
        if discovered:
            return discovered

    env_path = _candidate_tool_path(os.environ.get("GDB_DIR"), executable_name)
    if env_path:
        return env_path

    path_exe = shutil.which(executable_name)
    if path_exe:
        return path_exe

    for root in filter(None, [os.environ.get("TI_ROOT"), os.environ.get("CCS_BASE")]):
        discovered = _discover_file(root, executable_name)
        if discovered:
            return discovered

    return executable_name


def _posix_path(path: str) -> str:
    """Normalize a filesystem path for CMake/JSON by using forward slashes."""
    return str(Path(path)).replace("\\", "/")


def _resolve_openocd_scripts(openocd_exe: str) -> str:
    """Derive the OpenOCD scripts directory from the executable location.

    When the executable path is known, scripts are located relative to it.
    Otherwise falls back to searching the TI tool cache roots for an openocd
    installation and deriving the scripts directory from there.
    """
    if not openocd_exe:
        return ""

    exe_path = Path(openocd_exe)
    if exe_path.is_file() or exe_path.suffix.lower() == ".exe":
        base_dir = exe_path.parent.parent
        candidates = [
            base_dir / "openocd" / "scripts",
            base_dir / "share" / "openocd" / "scripts",
            exe_path.parent / ".." / "scripts",
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return str(candidate)

    # Fallback: search tool cache roots for an openocd installation,
    # then derive its scripts directory.
    for root in _tool_cache_roots():
        openocd_dir = _discover_dir(root, r"openocd")
        if openocd_dir:
            for sub in ["scripts", "share/openocd/scripts"]:
                candidate = os.path.join(openocd_dir, sub)
                if os.path.isdir(candidate):
                    return candidate

    return ""
    
def _cmake_cached_generator(build_dir: str) -> Optional[str]:
    """Read the generator recorded in an existing CMakeCache.txt, if any."""
    cache_file = os.path.join(build_dir, "CMakeCache.txt")
    if not os.path.isfile(cache_file):
        return None

    content = _read_text_file(cache_file)
    match = re.search(r"^CMAKE_GENERATOR:INTERNAL=(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    return None

# =============================================================================
# SDK metadata auto-discovery — no hardcoded chip table needed
# =============================================================================

# Module-level caches (cleared per SDK instance)
_sdk_metadata_cache: Dict[str, dict] = {}


def _load_tirex_json(sdk_dir: str) -> dict:
    """Load macros.tirex.json as a plain dict. Returns {} on failure."""
    tirex_path = os.path.join(sdk_dir, ".metadata", ".tirex", "macros.tirex.json")
    if not os.path.isfile(tirex_path):
        return {}
    try:
        with open(tirex_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _parse_device_family_h(sdk_dir: str) -> Dict[str, str]:
    """Parse DeviceFamily.h to map __DEVICE_DEFINE__ → PARENT_NAME.

    Returns dict like: {'__MSPM0G3519__': 'MSPM0GX51X', ...}
    """
    cache_key = f"device_family_{sdk_dir}"
    if cache_key in _sdk_metadata_cache:
        return _sdk_metadata_cache[cache_key]

    header_path = os.path.join(sdk_dir, "source", "ti", "devices", "DeviceFamily.h")
    device_to_parent: Dict[str, str] = {}

    if not os.path.isfile(header_path):
        warn(f"DeviceFamily.h not found: {header_path}")
        _sdk_metadata_cache[cache_key] = device_to_parent
        return device_to_parent

    content = _read_text_file(header_path)

    # Split on #elif blocks (also handles the first #if defined(...) line)
    blocks = re.split(r"#elif\s+", content)
    for block in blocks:
        defines = re.findall(r"__(\w+)__", block)
        parent_match = re.search(
            r"DeviceFamily_PARENT\s+DeviceFamily_PARENT_(\w+)", block
        )
        if parent_match and defines:
            parent = parent_match.group(1)
            for d in defines:
                device_to_parent[f"__{d}__"] = parent

    _sdk_metadata_cache[cache_key] = device_to_parent
    return device_to_parent


def _build_startup_index(sdk_dir: str) -> Dict[str, str]:
    """Scan GCC startup directory, return pattern → relative-path mapping.

    e.g. {'mspm0g351x': 'ti/devices/msp/m0p/startup_system_files/gcc/startup_mspm0g351x_gcc.c'}
    """
    cache_key = f"startup_index_{sdk_dir}"
    if cache_key in _sdk_metadata_cache:
        return _sdk_metadata_cache[cache_key]

    startup_dir = os.path.join(
        sdk_dir, "source", "ti", "devices", "msp", "m0p",
        "startup_system_files", "gcc",
    )
    index: Dict[str, str] = {}

    if not os.path.isdir(startup_dir):
        warn(f"Startup directory not found: {startup_dir}")
        _sdk_metadata_cache[cache_key] = index
        return index

    base_rel = os.path.join(
        "ti", "devices", "msp", "m0p", "startup_system_files", "gcc",
    )
    for fname in sorted(os.listdir(startup_dir)):
        if not fname.endswith("_gcc.c"):
            continue
        # startup_mspm0g351x_gcc.c → mspm0g351x
        pattern = fname.replace("startup_", "").replace("_gcc.c", "")
        index[pattern] = os.path.join(base_rel, fname)

    _sdk_metadata_cache[cache_key] = index
    return index


def _match_startup(device: str, startup_index: Dict[str, str]) -> str:
    """Match a device name to its GCC startup file.

    Algorithm: lower-case the device name, then progressively replace
    trailing digits with 'x' until a startup pattern matches.

    Returns the relative path to the startup .c file, or an empty string.
    """
    dl = device.lower()
    for i in range(len(dl) - 1, -1, -1):
        if dl[i].isdigit():
            candidate = dl[:i] + "x" + dl[i + 1 :]
            if candidate in startup_index:
                return startup_index[candidate]
        else:
            break
    return ""


def _resolve_driverlib(sdk_dir: str, device: str, parent_name: str = "") -> str:
    """Derive the driverlib .a path from the DeviceFamily_PARENT name.

    Falls back to macros.tirex.json grouping when the direct parent→directory
    mapping has no match (e.g. MSPS003Fx, MSP32 chips).
    """
    dl_base = os.path.join("ti", "driverlib", "lib", "gcc", "m0p")

    # --- Try direct parent → directory mapping ---
    if parent_name:
        dirname = parent_name.lower()
        candidate = os.path.join(sdk_dir, "source", dl_base, dirname, "driverlib.a")
        if os.path.isfile(candidate):
            return os.path.join(dl_base, dirname, "driverlib.a")

    # --- Fallback: find device in macros.tirex.json groups ---
    tirex = _load_tirex_json(sdk_dir)
    if tirex:
        device_upper = device.upper().rstrip("X")
        for item in tirex:
            name = item.get("arraymacro", "")
            if name.endswith("_devices") and device_upper in item.get("value", []):
                # e.g. MSPM0C110x_devices → mspm0c110x
                group_dir = name.replace("_devices", "").lower()
                candidate = os.path.join(
                    sdk_dir, "source", dl_base, group_dir, "driverlib.a"
                )
                if os.path.isfile(candidate):
                    return os.path.join(dl_base, group_dir, "driverlib.a")

    # --- Last resort ---
    warn(f"Could not resolve driverlib for {device}, using generic path")
    return os.path.join(dl_base, "mspm0g1x0x_g3x0x", "driverlib.a")


def _resolve_memory_from_lds(sdk_dir: str, device: str) -> dict:
    """Extract Flash/SRAM layout from the SDK's pre-built linker script.

    Returns dict with keys: flash_origin, flash_length, flash_kb,
    sram_origin, sram_length, sram_kb.
    """
    part_lower = device.lower().rstrip("x")
    lds_dir = os.path.join(
        sdk_dir, "source", "ti", "devices", "msp", "m0p", "linker_files", "gcc",
    )
    lds_path = os.path.join(lds_dir, f"{part_lower}.lds")

    # --- Try exact match ---
    if not os.path.isfile(lds_path):
        # --- Fallback 1: find sibling in same tirex group ---
        tirex = _load_tirex_json(sdk_dir)
        sibling_lds = None
        if tirex:
            device_upper = device.upper().rstrip("X")
            for item in tirex:
                name = item.get("arraymacro", "")
                if name.endswith("_devices") and device_upper in item.get("value", []):
                    for sibling in item["value"]:
                        sib_path = os.path.join(lds_dir, f"{sibling.lower()}.lds")
                        if os.path.isfile(sib_path):
                            sibling_lds = sib_path
                            break
                    break

        # --- Fallback 2: find sibling in same DeviceFamily_PARENT group ---
        if not sibling_lds:
            device_to_parent = _parse_device_family_h(sdk_dir)
            device_define = f"__{device.upper().rstrip('X')}__"
            parent = device_to_parent.get(device_define, "")
            if parent:
                siblings = [
                    d.strip("_") for d, p in device_to_parent.items()
                    if p == parent
                ]
                for sibling in siblings:
                    sib_path = os.path.join(lds_dir, f"{sibling.lower()}.lds")
                    if os.path.isfile(sib_path):
                        sibling_lds = sib_path
                        break

        if sibling_lds:
            lds_path = sibling_lds
        else:
            warn(f"No linker script for {device}, using default memory layout")
            return {
                "flash_origin": "0x00000000",
                "flash_length": "0x00020000",
                "flash_kb": 128,
                "sram_origin": "0x20200000",
                "sram_length": "0x00008000",
                "sram_kb": 32,
            }

    content = _read_text_file(lds_path)

    # Parse MEMORY { FLASH (RX) : ORIGIN = 0x..., LENGTH = 0x... ... }
    mem_match = re.search(r"MEMORY\s*{(.*?)}", content, re.DOTALL)
    if not mem_match:
        warn(f"Could not parse MEMORY block in {lds_path}")
        return {
            "flash_origin": "0x00000000",
            "flash_length": "0x00020000",
            "flash_kb": 128,
            "sram_origin": "0x20200000",
            "sram_length": "0x00008000",
            "sram_kb": 32,
        }

    mem_block = mem_match.group(1)
    regions: Dict[str, dict] = {}
    for m in re.finditer(
        r"(\w+)\s+\([^)]+\)\s*:\s*ORIGIN\s*=\s*(0x[0-9A-Fa-f]+),\s*LENGTH\s*=\s*(0x[0-9A-Fa-f]+)",
        mem_block,
    ):
        name = m.group(1)
        origin = m.group(2)
        length = int(m.group(3), 16)
        regions[name] = {"origin": origin, "length": m.group(3), "length_bytes": length}

    flash = regions.get("FLASH", {"origin": "0x00000000", "length": "0x00020000", "length_bytes": 0x20000})
    # Combine SRAM_BANK0 + SRAM_BANK1 (if present) for total SRAM.
    # Some L-series chips use "SRAM" instead of "SRAM_BANK0".
    sram0 = regions.get(
        "SRAM_BANK0",
        regions.get("SRAM", {"origin": "0x20200000", "length": "0x00008000", "length_bytes": 0x8000}),
    )
    sram1 = regions.get("SRAM_BANK1", {"origin": "", "length_bytes": 0})
    total_sram_bytes = sram0["length_bytes"] + sram1["length_bytes"]
    total_sram_hex = f"0x{total_sram_bytes:08X}"

    return {
        "flash_origin": flash["origin"],
        "flash_length": flash["length"],
        "flash_kb": flash["length_bytes"] // 1024,
        "sram_origin": sram0["origin"],
        "sram_length": total_sram_hex,
        "sram_kb": total_sram_bytes // 1024,
        "_lds_source": lds_path,
    }


def _generate_minimal_lds(mem: dict, device: str) -> str:
    """Generate a minimal GCC linker script from resolved memory layout.

    Used as a last resort when no pre-built .lds is available in the SDK.
    """
    return textwrap.dedent(f"""\
        MEMORY
        {{
            FLASH (RX)  : ORIGIN = {mem["flash_origin"]}, LENGTH = {mem["flash_length"]}
            SRAM  (RWX) : ORIGIN = {mem["sram_origin"]}, LENGTH = {mem["sram_length"]}
        }}

        _estack = {mem["sram_origin"]} + {mem["sram_length"]};

        SECTIONS
        {{
            .vectors :
            {{
                KEEP(*(.vectors))
            }} > FLASH

            .text :
            {{
                *(.text*)
                *(.rodata*)
            }} > FLASH

            .data : AT(LOADADDR(.text) + SIZEOF(.text))
            {{
                _data_start = .;
                *(.data*)
                _data_end = .;
            }} > SRAM

            .bss :
            {{
                _bss_start = .;
                *(.bss*)
                *(COMMON)
                _bss_end = .;
            }} > SRAM
        }}
    """)


# Debugger OpenOCD config mapping
DEBUGGER_CONFIG = {
    "cmsis-dap": {
        "configFiles": ["interface/cmsis-dap.cfg", "target/ti_mspm0.cfg"],
    },
    "xds110": {
        "configFiles": ["interface/xds110.cfg", "target/ti_mspm0.cfg"],
    },
    "jlink": {
        "configFiles": ["interface/jlink.cfg", "target/ti_mspm0.cfg"],
    },
}


# =============================================================================
# ANSI colors
# =============================================================================
class Color:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def info(msg: str):
    print(f"{Color.BLUE}[INFO]{Color.RESET} {msg}")


def success(msg: str):
    print(f"{Color.GREEN}[OK]{Color.RESET}   {msg}")


def warn(msg: str):
    print(f"{Color.YELLOW}[WARN]{Color.RESET} {msg}")


def error(msg: str):
    print(f"{Color.RED}[ERROR]{Color.RESET} {msg}", file=sys.stderr)


# =============================================================================
# Step 1: Parse arguments
# =============================================================================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TI MSPM0 一键嵌入式项目初始化工具 — 从 SysConfig 配置自动生成完整项目",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_build_help_epilog(),
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="自检开发环境：检查 arm-gcc、CMake、SysConfig、SDK、OpenOCD 等工具链是否就绪",
    )

    sub = parser.add_subparsers(dest="command", help="子命令（可省略，工具会自动判断上下文）")

    # ---- subcommand: new ----
    p_new = sub.add_parser(
        "new",
        help="创建新的 MSPM0 项目",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            使用示例:
              # 自动发现当前目录的 .syscfg
              %(prog)s -n my_project

              # 指定 .syscfg 文件 + XDS110 调试器
              %(prog)s myboard.syscfg -n uart_echo -d xds110

              # 无 .syscfg，纯裸机起点（SDK 自动发现芯片参数）
              %(prog)s --device MSPM0G3519 --package "LQFP-100(PZ)" -n my_project

              # JLink 调试器
              %(prog)s -n my_project -d jlink

              # 预览模式：只看不建
              %(prog)s -n test_proj --dry-run
        """),
    )
    p_new.add_argument(
        "syscfg",
        nargs="?",
        help="SysConfig 项目文件 (.syscfg)。省略时自动从当前目录发现",
    )
    p_new.add_argument("-n", "--name", required=True, help="项目名称 (CMake project name)")
    p_new.add_argument("-o", "--output", default=None, help="输出目录（默认 ./<项目名>/）")
    p_new.add_argument("-s", "--sdk", default=DEFAULT_SDK_DIR, help=f"MSPM0 SDK 路径 (默认: {DEFAULT_SDK_DIR})")
    p_new.add_argument("--sysconfig", default=DEFAULT_SYSCONFIG_DIR, help=f"SysConfig 安装目录 (默认: {DEFAULT_SYSCONFIG_DIR})")
    p_new.add_argument("-d", "--debugger", choices=["cmsis-dap", "xds110", "jlink", "none"], default="cmsis-dap", help="调试器类型：cmsis-dap (默认), xds110, jlink, none")
    p_new.add_argument("--device", default=None, help="手动指定芯片型号（如 MSPM0G3507）。SDK 支持的任意型号均可，无需硬编码")
    p_new.add_argument("--package", default=None, help="手动指定封装（如 LQFP-48(PT)）")
    p_new.add_argument(
        "--openocd", "--openocd-path",
        dest="openocd", default=None,
        help="OpenOCD 可执行文件或目录；覆盖自动搜索（通常无需设置）",
    )
    p_new.add_argument(
        "--gdb", "--gdb-path",
        dest="gdb", default=None,
        help="arm-none-eabi-gdb 可执行文件或目录；覆盖自动搜索（通常无需设置）",
    )
    p_new.add_argument("--dry-run", action="store_true", help="预览模式：仅显示操作，不创建文件")
    p_new.add_argument("--no-build", action="store_true", help="跳过 cmake configure + build 验证")
    p_new.add_argument("--no-git", action="store_true", help="禁止 Git 初始化（即使系统安装了 Git）")

    # ---- subcommand: regenerate ----
    p_regen = sub.add_parser(
        "regenerate",
        help="为已有项目重新运行 SysConfig 生成代码",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            使用示例:
              # 在项目目录内直接运行
              %(prog)s

              # 指定项目路径
              %(prog)s /path/to/project

              # 跳过构建验证
              %(prog)s --no-build

              修改 .syscfg 引脚/外设配置后运行此命令，自动重新生成配置文件。
              手写的 src/ 目录代码不会被修改。旧文件备份到 .sysconfig_backup/。
        """),
    )
    p_regen.add_argument("project_dir", nargs="?", default=".", help="项目目录（默认当前目录）")
    p_regen.add_argument("-s", "--sdk", default=DEFAULT_SDK_DIR, help=f"MSPM0 SDK 路径")
    p_regen.add_argument("--sysconfig", default=DEFAULT_SYSCONFIG_DIR, help=f"SysConfig 安装目录")
    p_regen.add_argument(
        "--openocd", "--openocd-path",
        dest="openocd", default=None,
        help="OpenOCD 可执行文件或目录",
    )
    p_regen.add_argument(
        "--gdb", "--gdb-path",
        dest="gdb", default=None,
        help="arm-none-eabi-gdb 可执行文件或目录",
    )
    p_regen.add_argument(
        "-d", "--debugger",
        choices=["cmsis-dap", "xds110", "jlink", "none"],
        default="cmsis-dap",
        help="调试器类型：cmsis-dap (默认), xds110, jlink, none",
    )
    p_regen.add_argument("--no-build", action="store_true", help="跳过重编译验证")
    p_regen.add_argument("--backup", action="store_true", default=True, help="覆盖前备份旧文件到 .sysconfig_backup/ (默认开启)")
    p_regen.add_argument("--no-backup", action="store_false", dest="backup", help="禁用备份")
    p_regen.add_argument("--dry-run", action="store_true", help="预览模式")
    p_regen.add_argument("--no-git", action="store_true", help="禁止 Git 初始化")

    # ---- subcommand: check ----
    sub.add_parser(
        "check",
        help="自检开发环境：检查 arm-gcc、CMake、Ninja、SysConfig、SDK、OpenOCD 等",
    )

    return parser.parse_args()


def _build_help_epilog() -> str:
    """Build the comprehensive help epilog used by the top-level --help."""
    return textwrap.dedent(f"""\
    ══════════════════════════════════════════════════════════════════════════════
                              MSPM0-INIT  完整使用教程
    ══════════════════════════════════════════════════════════════════════════════

    ── 快速开始 ─────────────────────────────────────────────────────────────────

      1. 用 TI SysConfig GUI 配好芯片、引脚和外设，保存 .syscfg 到一个空目录
      2. 在该目录下运行:
           mspm0-init
      3. 构建:
           cmake --build build -j$(nproc)
      4. VSCode 调试:
           code .
           F5 → 选择 CMSIS-DAP / XDS110 / JLink

    ── 子命令 ───────────────────────────────────────────────────────────────────

      mspm0-init                 无参数：自动检测上下文
                                   - 目录有 .syscfg + CMakeLists.txt → 自动 regenerate
                                   - 目录仅有 .syscfg → 自动以文件名创建项目
                                   - 目录为空 → 显示帮助
      mspm0-init new             创建新项目
      mspm0-init regenerate      重新生成 SysConfig 配置（保留手写代码）
      mspm0-init check           环境自检
      mspm0-init --check         环境自检（全局参数，位置无关）

    ── 调试器选项 (-d) ─────────────────────────────────────────────────────────

      -d cmsis-dap    板载 CMSIS-DAP 调试器（LaunchPad 默认）
      -d xds110       TI XDS110 调试器
      -d jlink        SEGGER J-Link 调试器（需 TI 定制版 OpenOCD）
      -d none         不生成调试配置

      JLink 注意：当前 TI SDK 附带的 OpenOCD 已包含 interface/jlink.cfg，
      直接 -d jlink 即可使用。如使用 Segger 官方 JLink GDB Server，需手动修改
      生成的 .vscode/launch.json。

    ── 芯片型号 (--device) ──────────────────────────────────────────────────────

      支持 SDK (DeviceFamily.h) 中收录的全部 58 款 MSPM0 芯片，无需硬编码:
        MSPM0G系列: G1105~G1107, G1207, G1218, G1505~G1507, G1518~G1519,
                    G3105~G3107, G3207, G3218, G3505~G3507, G3518~G3519,
                    G3529, G5115~G5117, G5187
        MSPM0L系列: L1105~L1106, L1116~L1117, L1126~L1127, L1226~L1228,
                    L1303~L1306, L1343~L1346, L2116~L2117, L2226~L2228
        MSPM0C系列: C1103~C1106
        MSPM0H系列: H3215~H3216
        MSP32系列:  G031C6~G031C8, C031C6
        MSPS系列:   003F3~003F4

      从 .syscfg 自动获取时无需关心型号。手动指定时用 --device。
      工具会自动从 SDK 中匹配 startup 文件、driverlib 和内存布局。

    ── 环境变量（全部可选）─────────────────────────────────────────────────────

      MSPM0_SDK        MSPM0 SDK 根目录  (默认: ~/ti/mspm0_sdk_*/)
      SYSCONFIG_DIR    SysConfig 安装目录 (默认: ~/ti/sysconfig_*/)
      TI_ROOT          TI 工具根目录      (Linux: ~/ti, Windows: C:\\ti)
      OPENOCD_DIR      OpenOCD 目录或可执行文件
      GDB_DIR          arm-none-eabi-gdb 目录

      推荐在 ~/.zshrc 或 ~/.bashrc 中配置:
        export MSPM0_SDK=~/ti/mspm0_sdk_2_10_00_04
        export SYSCONFIG_DIR=~/ti/sysconfig_1.27.1

    ── 使用技巧 ─────────────────────────────────────────────────────────────────

      • 在空目录中放置 .syscfg 后直接 mspm0-init，无需记住任何参数
      • 修改引脚/外设后运行 mspm0-init regenerate，手写代码安全无虞
      • --dry-run 预览模式先看看会生成什么，确认后再正式运行
      • --no-build 跳过构建验证，适合还未安装完整工具链时预览
      • --no-git 跳过 Git 仓库初始化（默认检测到 git 则自动 git init）
      • VSCode 中 Ctrl+Shift+P → Run Task → Open SysConfig 直接打开配置界面
      • 旧项目先 mspm0-init check 诊断环境，再逐步修复
      • regenerate 默认会自动备份旧文件到 .sysconfig_backup/
      • 生成的 .vscode/ 配置可直接用于 VSCode + Cortex-Debug 插件
      • Windows 用户: TI 工具需安装在 C:\\ti\\，或设置对应的环境变量

    ── 生成的项目结构 ───────────────────────────────────────────────────────────
      my_project/
      ├── CMakeLists.txt              # CMake 构建定义
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
      ├── build/                      # 构建输出 (ELF/HEX/BIN/MAP)
      └── .vscode/
            ├── launch.json           # 调试器配置
            ├── tasks.json            # 构建任务
            └── c_cpp_properties.json # IntelliSense 配置

    ── 手动烧录 (OpenOCD) ───────────────────────────────────────────────────────
      openocd -f interface/cmsis-dap.cfg -f target/ti_mspm0.cfg \\
        -c "program build/project.elf verify reset exit"

      # JLink
      openocd -f interface/jlink.cfg -f target/ti_mspm0.cfg \\
        -c "program build/project.elf verify reset exit"

    ══════════════════════════════════════════════════════════════════════════════
    """)


# =============================================================================
# Step 1b: Validate environment
# =============================================================================
def validate_environment(args: argparse.Namespace) -> bool:
    """Check that all required tools are available."""
    ok = True

    # arm-none-eabi-gcc
    gcc = shutil.which("arm-none-eabi-gcc")
    if not gcc:
        error("arm-none-eabi-gcc not found. Install: sudo apt install gcc-arm-none-eabi")
        ok = False
    else:
        success(f"arm-none-eabi-gcc: {gcc}")

    # arm-none-eabi-objcopy
    objcopy = shutil.which("arm-none-eabi-objcopy")
    if not objcopy:
        error("arm-none-eabi-objcopy not found")
        ok = False

    # SysConfig CLI (Called via shell script, internally launches node)
    sysconfig_cli = os.path.join(args.sysconfig, _SYSCONFIG_CLI_NAME)
    if not os.path.isfile(sysconfig_cli):
        error(f"SysConfig CLI not found: {sysconfig_cli}")
        error("Set SYSconfig_DIR env var or use --sysconfig to specify path")
        ok = False
    else:
        args._sysconfig_cli = sysconfig_cli
        success(f"SysConfig CLI: {sysconfig_cli}")

    # SDK
    product_json = os.path.join(args.sdk, ".metadata", "product.json")
    if not os.path.isfile(product_json):
        error(f"MSPM0 SDK not found (missing product.json): {args.sdk}")
        error("Set MSPM0_SDK env var or use --sdk to specify path")
        ok = False
    else:
        success(f"MSPM0 SDK: {args.sdk}")

    # If syscfg file provided, verify it exists
    if args.syscfg:
        if not os.path.isfile(args.syscfg):
            error(f"SysConfig file not found: {args.syscfg}")
            ok = False
    else:
        # --device is required when no syscfg is provided
        if not args.device:
            error("Provide a .syscfg file or specify --device")
            ok = False

    return ok


def has_git() -> bool:
    """Check if git is installed on the system."""
    return shutil.which("git") is not None


def init_git(project_dir: str, dry_run: bool = False) -> bool:
    """Run git init and write a .gitignore in the project directory.

    Returns True on success, False if git init failed.
    """
    if dry_run:
        info("[dry-run] git init + .gitignore")
        return True
    try:
        subprocess.run(
            ["git", "init"], cwd=project_dir,
            check=True, capture_output=True, text=True,
        )
        # Write .gitignore (don't overwrite existing)
        gitignore_path = os.path.join(project_dir, ".gitignore")
        if not os.path.isfile(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(GITIGNORE_TEMPLATE)
        success("Git repository initialized (.gitignore added)")
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        warn(f"git init failed: {e}")
        return False


def cmd_check(args: argparse.Namespace):
    """Check development environment and report status of all required tools."""
    print()
    info("TI Project Assistant — Environment Check")
    info(f"Platform: {'Windows' if IS_WIN else 'Linux'}")
    info(f"Python: v{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print()

    all_ok = True

    def check_item(name: str, ok: bool, detail: str, required: bool = True):
        nonlocal all_ok
        if ok:
            success(f"[OK] {name}: {detail}")
        elif required:
            error(f"[MISSING] {name}: {detail}")
            all_ok = False
        else:
            warn(f"[OPTIONAL] {name}: {detail}")

    # 1) Python version
    py_ok = sys.version_info >= (3, 8)
    check_item("Python", py_ok,
               f"v{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
               if py_ok else f"v{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (need ≥ 3.8)")

    # 2) arm-none-eabi-gcc
    gcc = shutil.which("arm-none-eabi-gcc")
    check_item("ARM GCC", gcc is not None, gcc or "not found — install gcc-arm-none-eabi")

    # 3) arm-none-eabi-objcopy
    objcopy = shutil.which("arm-none-eabi-objcopy")
    check_item("ARM objcopy", objcopy is not None, objcopy or "not found (bundled with ARM GCC)")

    # 4) CMake
    cmake = shutil.which("cmake")
    check_item("CMake", cmake is not None, cmake or "not found — install cmake")

    # 5) Ninja
    ninja = shutil.which("ninja")
    check_item("Ninja", ninja is not None, ninja or "not found — install ninja-build")

    # 6) ARM GDB
    gdb = _resolve_gdb_exe()
    gdb_ok = os.path.isfile(gdb) or shutil.which(gdb) is not None
    check_item("ARM GDB", gdb_ok, gdb if gdb_ok else "not found — install arm-none-eabi-gdb")

    # 7) SysConfig CLI
    sysconfig_dir = _resolve_sysconfig()
    cli_path = os.path.join(sysconfig_dir, _SYSCONFIG_CLI_NAME)
    cli_ok = os.path.isfile(cli_path)
    check_item("SysConfig CLI", cli_ok,
               cli_path if cli_ok else f"not found — install SysConfig to ~/ti/ (checked: {sysconfig_dir})")

    # 8) MSPM0 SDK
    sdk_dir = _resolve_sdk()
    product_json = os.path.join(sdk_dir, ".metadata", "product.json")
    sdk_ok = os.path.isfile(product_json)
    check_item("MSPM0 SDK", sdk_ok,
               sdk_dir if sdk_ok else f"not found — install MSPM0 SDK to ~/ti/ (checked: {sdk_dir})")

    # 9) OpenOCD
    openocd = _resolve_openocd_exe()
    openocd_ok = os.path.isfile(openocd) or shutil.which(openocd) is not None
    check_item("OpenOCD", openocd_ok,
               openocd if openocd_ok else "not found — install via VSCode TI plugin or CCS Theia")

    # 10) Git (optional)
    git_bin = shutil.which("git")
    check_item("Git", git_bin is not None,
               git_bin or "not found — 项目将不启用版本控制",
               required=False)

    # Summary
    print()
    cmake_gen = _CMAKE_GENERATOR
    info(f"CMake generator: {cmake_gen}")
    info(f"TI tools base:  {_TI_BASE}")

    print()
    if all_ok:
        success("All checks passed! Environment is ready for MSPM0 development.")
    else:
        error("Some checks failed. Install the missing dependencies listed above.")

    return all_ok


# =============================================================================
# Step 2: Parse syscfg to extract device/package from @cliArgs
# =============================================================================
def parse_syscfg_metadata(syscfg_path: str) -> dict:
    """Read @v2CliArgs and @cliArgs from .syscfg file."""
    metadata = {"device": None, "package": None, "part": "Default"}
    if not syscfg_path or not os.path.isfile(syscfg_path):
        return metadata

    content = _read_text_file(syscfg_path)

    # Prefer v2CliArgs: //@v2CliArgs --device "MSPM0G3507" --package "LQFP-48(PT)"
    v2 = re.search(r"@v2CliArgs\s+(.*)", content)
    if v2:
        args_str = v2.group(1)
    else:
        cli = re.search(r"@cliArgs\s+(.*)", content)
        if cli:
            args_str = cli.group(1)
        else:
            return metadata

    # Extract --device
    dev = re.search(r'--device\s+"([^"]+)"', args_str)
    if dev:
        metadata["device"] = dev.group(1)

    # Extract --package
    pkg = re.search(r'--package\s+"([^"]+)"', args_str)
    if pkg:
        metadata["package"] = pkg.group(1)

    # Extract --part
    part = re.search(r'--part\s+"([^"]+)"', args_str)
    if part:
        metadata["part"] = part.group(1)

    return metadata


# =============================================================================
# Step 2b: Invoke SysConfig CLI
# =============================================================================
def run_sysconfig(
    syscfg_path: str,
    out_dir: str,
    device: str,
    package: str,
    sdk_dir: str,
    sysconfig_cli: str,
    dry_run: bool = False,
) -> bool:
    """Invoke SysConfig CLI to generate code files."""
    product_json = os.path.join(sdk_dir, ".metadata", "product.json")

    cmd = [
        sysconfig_cli,
        "--product", product_json,
        "--device", device,
        "--package", package,
        "--script", syscfg_path,
        "--output", out_dir,
        "--compiler", "gcc",
    ]

    info(f"Execute: {' '.join(cmd)}")

    if dry_run:
        info("[dry-run] Skipping actual execution")
        return True

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error(f"SysConfig CLI failed:\n{result.stderr}\n{result.stdout}")
        return False

    success("SysConfig code generation complete")
    generated = os.listdir(out_dir)
    info(f"Generated files ({len(generated)}): {', '.join(generated)}")
    return True


# =============================================================================
# Step 3: Parse ti_msp_dl_config.h for metadata
# =============================================================================
def parse_dl_config(dl_config_h: str) -> dict:
    """Extract chip defines, pin configs, and clock info from generated ti_msp_dl_config.h."""
    meta = {
        "chip_defines": [],
        "cpu_freq_hz": 32000000,
        "pin_groups": [],
    }

    if not os.path.isfile(dl_config_h):
        warn(f"NotFound: {dl_config_h}, using default metadata")
        return meta

    content = _read_text_file(dl_config_h)

    # #define CONFIG_MSPM0G350X / #define CONFIG_MSPM0G3507
    meta["chip_defines"] = re.findall(r"#define\s+(CONFIG_\w+)", content)

    # #define CPUCLK_FREQ  32000000
    freq = re.search(r"#define\s+CPUCLK_FREQ\s+(\d+)", content)
    if freq:
        meta["cpu_freq_hz"] = int(freq.group(1))

    # Pin groups: GPIO_GRP_0_PORT → GPIOA, GPIO_GRP_0_LED0_PIN → DL_GPIO_PIN_14
    groups: Dict[str, dict] = {}
    for m in re.finditer(r"#define\s+(\w+)_PORT\s+\((\w+)\)", content):
        grp_name = m.group(1)  # e.g. GPIO_GRP_0
        groups[grp_name] = {"name": grp_name, "port": m.group(2), "pins": []}

    for m in re.finditer(r"#define\s+(\w+)_(\w+)_PIN\s+\((\w+)\)", content):
        grp_name = m.group(1)       # e.g. GPIO_GRP_0
        pin_name = m.group(2)       # e.g. LED0
        pin_val  = m.group(3)       # e.g. DL_GPIO_PIN_14
        if grp_name in groups:
            groups[grp_name]["pins"].append({"name": pin_name, "define": pin_val})

    for m in re.finditer(r"#define\s+(\w+)_(\w+)_IOMUX\s+\((\w+)\)", content):
        grp_name = m.group(1)
        pin_name = m.group(2)
        iomux_val = m.group(3)
        if grp_name in groups:
            for pin in groups[grp_name]["pins"]:
                if pin["name"] == pin_name:
                    pin["iomux"] = iomux_val

    meta["pin_groups"] = list(groups.values())
    return meta


# =============================================================================
# Step 3b: Extract GCC define from device.opt
# =============================================================================
def parse_device_opt(device_opt_path: str) -> str:
    """Extract -D macro defines from device.opt."""
    if not os.path.isfile(device_opt_path):
        return ""
    content = _read_text_file(device_opt_path)
    defines = re.findall(r"-D(\w+)", content)
    return defines[0] if defines else ""


# =============================================================================
# Step 3c: Generate stub ti_msp_dl_config.c/h when SysConfig produces none
# (blank .syscfg with no peripherals configured)
# =============================================================================
DL_CONFIG_H_STUB = """\
/*
 *  ============ ti_msp_dl_config.h =============
 *  Minimal stub — no peripherals configured in SysConfig.
 *  Re-run SysConfig after adding pins/peripherals to replace this file.
 */

#ifndef ti_msp_dl_config_h
#define ti_msp_dl_config_h

{config_defines}

#if defined(__GNUC__)
#define SYSCONFIG_WEAK __attribute__((weak))
#elif defined(__IAR_SYSTEMS_ICC__)
#define SYSCONFIG_WEAK __weak
#elif defined(__ti_version__) || defined(__TI_COMPILER_VERSION__)
#define SYSCONFIG_WEAK __attribute__((weak))
#else
#define SYSCONFIG_WEAK
#endif

#include <ti/devices/msp/msp.h>
#include <ti/driverlib/driverlib.h>
#include <ti/driverlib/m0p/dl_core.h>

#ifdef __cplusplus
extern "C" {{
#endif

#define CPUCLK_FREQ                                                    32000000

void SYSCFG_DL_init(void);

#ifdef __cplusplus
}}
#endif

#endif /* ti_msp_dl_config_h */
"""

DL_CONFIG_C_STUB = """\
/*
 *  ============ ti_msp_dl_config.c =============
 *  Minimal stub — no peripherals configured in SysConfig.
 *  Re-run SysConfig after adding pins/peripherals to replace this file.
 */

#include "ti_msp_dl_config.h"

SYSCONFIG_WEAK void SYSCFG_DL_init(void)
{{
    /* No peripherals configured yet.
     * Add pins/peripherals in SysConfig and regenerate to populate. */
}}
"""


def write_dl_config_stubs(out_dir: str, device: str, sdk_dir: str = "", dry_run: bool = False):
    """Generate minimal ti_msp_dl_config.c/h when SysConfig doesn't.

    Writes flat into out_dir (SysConfig temp dir) — distribute_files()
    will route them to config/ in the project tree.

    Also copies the SDK pre-built linker script when available, so that
    --device mode (no .syscfg) produces a buildable project.
    """
    h_path = os.path.join(out_dir, "ti_msp_dl_config.h")
    c_path = os.path.join(out_dir, "ti_msp_dl_config.c")

    if os.path.isfile(h_path) and os.path.isfile(c_path):
        return  # Already exist, nothing to do

    # Build CONFIG_* defines from device name
    normalized = device.upper().rstrip("X")
    config_defines = f"#define CONFIG_{normalized}X\n#define CONFIG_{normalized}"

    if not os.path.isfile(h_path):
        content_h = DL_CONFIG_H_STUB.format(config_defines=config_defines)
        if dry_run:
            info(f"[dry-run] Write stub ti_msp_dl_config.h")
        else:
            with open(h_path, "w", encoding="utf-8") as f:
                f.write(content_h)
            info("  + ti_msp_dl_config.h (stub — no peripherals configured)")

    if not os.path.isfile(c_path):
        if dry_run:
            info(f"[dry-run] Write stub ti_msp_dl_config.c")
        else:
            with open(c_path, "w", encoding="utf-8") as f:
                f.write(DL_CONFIG_C_STUB)
            info("  + ti_msp_dl_config.c (stub — no peripherals configured)")

    # ── Copy SDK linker script for --device mode (no SysConfig) ──
    if sdk_dir:
        lds_path = os.path.join(out_dir, "device_linker.lds")
        opt_path = os.path.join(out_dir, "device.opt")
        if not os.path.isfile(lds_path):
            mem = _resolve_memory_from_lds(sdk_dir, device)
            sdk_lds_src = mem.get("_lds_source", "")
            if sdk_lds_src and os.path.isfile(sdk_lds_src):
                if dry_run:
                    info(f"[dry-run] cp {sdk_lds_src} → device_linker.lds")
                else:
                    shutil.copy2(sdk_lds_src, lds_path)
                    info("  + device_linker.lds (from SDK)")
            else:
                # Fallback: generate a minimal linker script from resolved memory
                lds_content = _generate_minimal_lds(mem, device)
                if dry_run:
                    info(f"[dry-run] Write device_linker.lds (minimal)")
                else:
                    with open(lds_path, "w", encoding="utf-8") as f:
                        f.write(lds_content)
                    info("  + device_linker.lds (minimal — verify memory layout)")
        if not os.path.isfile(opt_path):
            if dry_run:
                info(f"[dry-run] Write device.opt (empty)")
            else:
                with open(opt_path, "w", encoding="utf-8") as f:
                    f.write("")
                info("  + device.opt (empty — no SysConfig flags)")


# =============================================================================
# Step 4: Chip mapping — fully dynamic via SDK introspection
# =============================================================================
def resolve_chip(device: str, sdk_dir: str) -> dict:
    """Auto-discover chip parameters from the SDK (no hardcoded table).

    Uses:
      - DeviceFamily.h to map device→parent (for driverlib grouping)
      - Startup file directory scan + pattern matching
      - Pre-built linker scripts in linker_files/gcc/ for memory layout
      - macros.tirex.json as fallback for driverlib/lds edge cases
    """
    normalized = device.upper().rstrip("X")
    device_define = f"__{normalized}__"

    # 1. Parse DeviceFamily.h → get parent family name
    device_to_parent = _parse_device_family_h(sdk_dir)
    parent_name = device_to_parent.get(device_define, "")

    if not parent_name:
        warn(f"Chip {device} not found in DeviceFamily.h, using generic defaults")

    # 2. Match startup file
    startup_index = _build_startup_index(sdk_dir)
    startup = _match_startup(device, startup_index)

    if not startup:
        warn(f"No startup file matched for {device}, using best-guess path")
        startup = (
            f"ti/devices/msp/m0p/startup_system_files/gcc/"
            f"startup_{normalized.lower()}_gcc.c"
        )

    # 3. Resolve driverlib
    driverlib = _resolve_driverlib(sdk_dir, device, parent_name)

    # 4. Resolve memory layout from pre-built linker script
    memory = _resolve_memory_from_lds(sdk_dir, device)

    return {
        "cpu": "cortex-m0plus",
        "startup": startup,
        "driverlib": driverlib,
        "flash_kb": memory["flash_kb"],
        "sram_kb": memory["sram_kb"],
        "flash_origin": memory["flash_origin"],
        "flash_length": memory["flash_length"],
        "sram_origin": memory["sram_origin"],
        "sram_length": memory["sram_length"],
        "device_define": device_define,
        "device_name": normalized,
        "package_options": [],
    }


# =============================================================================
# Step 5: Create project directory structure
# =============================================================================
DIRS = [
    "config",
    "inc/app",
    "inc/driver",
    "inc/modules",
    "inc/utils",
    "src/app",
    "src/driver",
    "src/modules",
    "src/utils",
    "lib",
    "excluded",
    ".vscode",
    "build",
]


def create_directories(project_dir: str, dry_run: bool = False):
    """Create standard project directory tree."""
    for d in DIRS:
        full = os.path.join(project_dir, d)
        if dry_run:
            info(f"[dry-run] mkdir -p {{full}}")
        else:
            os.makedirs(full, exist_ok=True)
    success(f"Directory structure created ({len(DIRS)} subdirs)")


# =============================================================================
# Step 6: Distribute files
# =============================================================================
FILE_ROUTING = {
    # SysConfig output -> project location
    "ti_msp_dl_config.h":  "{project}/config",
    "ti_msp_dl_config.c":  "{project}/config",
    "device_linker.lds":   "{project}/config",
    "device.opt":          "{project}/config",
    "device_linker.cmd":   "{project}/excluded",
    "device.cmd.genlibs":  "{project}/excluded",
    "device.lds.genlibs":  "{project}/excluded",
    "Event.dot":           "{project}/excluded",
}


def distribute_files(sysconfig_out: str, project_dir: str, dry_run: bool = False):
    """Move SysConfig output files to their correct project locations."""
    for filename, dest_rel in FILE_ROUTING.items():
        src = os.path.join(sysconfig_out, filename)
        dest_dir = dest_rel.format(project=project_dir)
        dest = os.path.join(dest_dir, filename)

        if not os.path.isfile(src):
            continue

        if dry_run:
            info(f"[dry-run] cp {src} → {dest}")
            continue

        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(src, dest)
        info(f"  ✓ {filename}")

    # Also copy original syscfg to project root
    # (handled in write_templates)

    success("File distribution complete")


# =============================================================================
# Step 7: Template - CMakeLists.txt
# =============================================================================
CMAKE_TEMPLATE = textwrap.dedent("""\
    cmake_minimum_required(VERSION 3.13)

    set(CMAKE_SYSTEM_NAME Generic)
    set(CMAKE_SYSTEM_PROCESSOR cortex-m0plus)

    set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

    project({project_name} C ASM)

    # ===== Toolchain =====
    set(CMAKE_C_COMPILER   arm-none-eabi-gcc)
    set(CMAKE_CXX_COMPILER arm-none-eabi-g++)
    set(CMAKE_ASM_COMPILER arm-none-eabi-gcc)
    set(CMAKE_OBJCOPY      arm-none-eabi-objcopy)
    set(CMAKE_SIZE         arm-none-eabi-size)
    set(CMAKE_EXECUTABLE_SUFFIX .elf)

    set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

    # ===== MSPM0 SDK path =====
    set(SDK_DIR {sdk_dir}/source)
    set(DL_LIB  ${{SDK_DIR}}/{driverlib_path})

    # ===== Chip defines =====
    set(MCU_FLAGS_STR "-mcpu={cpu} -mthumb")
    separate_arguments(MCU_FLAGS UNIX_COMMAND ${{MCU_FLAGS_STR}})

    set(DEFINES_STR "{defines_str}")
    separate_arguments(DEFINES UNIX_COMMAND ${{DEFINES_STR}})

    # ===== Compile options =====
    add_compile_options(${{MCU_FLAGS}})
    add_compile_options(-std=gnu11 -Wall -Wextra -g -O0)
    add_compile_options(-ffunction-sections -fdata-sections)
    foreach(d ${{DEFINES}})
        add_compile_options(-D${{d}})
    endforeach()

    # ===== Link options =====
    add_link_options(${{MCU_FLAGS}})
    add_link_options(-T ${{CMAKE_SOURCE_DIR}}/config/device_linker.lds)
    add_link_options(-Wl,-Map=${{PROJECT_BINARY_DIR}}/${{PROJECT_NAME}}.map,--cref)
    add_link_options(-Wl,--gc-sections)
    add_link_options(--specs=nosys.specs -nostartfiles)

    # ===== Source files (auto-discover from src/ directories) =====
    file(GLOB_RECURSE PROJECT_SOURCES
        "src/*.c"
        "src/*.s"
        "src/*.S"
    )

    # ===== Executable =====
    add_executable(${{PROJECT_NAME}}
        ${{PROJECT_SOURCES}}
        config/ti_msp_dl_config.c
        ${{SDK_DIR}}/{startup_path}
    )

    # ===== Include paths =====
    target_include_directories(${{PROJECT_NAME}} PRIVATE
        ${{CMAKE_SOURCE_DIR}}
        ${{CMAKE_SOURCE_DIR}}/config
        ${{CMAKE_SOURCE_DIR}}/inc
        ${{CMAKE_SOURCE_DIR}}/inc/app
        ${{CMAKE_SOURCE_DIR}}/inc/driver
        ${{CMAKE_SOURCE_DIR}}/inc/modules
        ${{CMAKE_SOURCE_DIR}}/inc/utils
        ${{SDK_DIR}}
        ${{SDK_DIR}}/third_party/CMSIS/Core/Include
    )

    # ===== Link driverlib =====
    target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{DL_LIB}})

    # ===== Post-build: .hex (flash prog) + .bin (bootloader) + size =====
    add_custom_command(TARGET ${{PROJECT_NAME}} POST_BUILD
        COMMAND ${{CMAKE_OBJCOPY}} -O ihex $<TARGET_FILE:${{PROJECT_NAME}}>
                ${{PROJECT_BINARY_DIR}}/${{PROJECT_NAME}}.hex
        COMMAND ${{CMAKE_OBJCOPY}} -O binary $<TARGET_FILE:${{PROJECT_NAME}}>
                ${{PROJECT_BINARY_DIR}}/${{PROJECT_NAME}}.bin
        COMMAND ${{CMAKE_SIZE}} --format=berkeley $<TARGET_FILE:${{PROJECT_NAME}}>
        COMMENT "Generating hex, bin and size info"
    )""")


# =============================================================================
# Step 7b: Template - main.c
# =============================================================================
MAIN_C_TEMPLATE = """\
#include "ti_msp_dl_config.h"

static void delay_ms(uint32_t ms)
{{
    delay_cycles(ms * (CPUCLK_FREQ / 1000));
}}

int main(void)
{{
    SYSCFG_DL_init();

    while (1) {{
        /* TODO: Add your application logic here */
        delay_ms(1000);
    }}
}}
"""


# =============================================================================
# Step 7c: Template - main.h
# =============================================================================
MAIN_H_TEMPLATE = textwrap.dedent("""\
    /**
     * @file    main.h
     * @brief   {project_name} application header
     */

    #ifndef MAIN_H_
    #define MAIN_H_

    #include "ti_msp_dl_config.h"

    /* Global macros */
    #define APP_VERSION_MAJOR  0
    #define APP_VERSION_MINOR  1

    #endif /* MAIN_H_ */
    """)


# =============================================================================
# Step 7d: Template - .gitignore
# =============================================================================
GITIGNORE_TEMPLATE = """\
# Build output
build/
*.elf
*.hex
*.bin
*.map
*.o
*.d

# SysConfig temp
.sysconfig_tmp/
.sysconfig_backup/

# IDE
.vscode/
.DS_Store
Thumbs.db
"""


# =============================================================================
# Step 8: Template - .vscode/tasks.json
# =============================================================================
TASKS_JSON_TEMPLATE = """\
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "CMake Configure",
            "type": "shell",
            "command": "cmake",
            "args": [
                "-B", "build",
                "-G", "___CMAKE_GENERATOR___",
                "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                "."
            ],
            "group": "build",
            "problemMatcher": [],
            "options": {
                "cwd": "${workspaceFolder}"
            }
        },
        {
            "label": "Build MSPM0 project",
            "type": "shell",
            "command": "cmake",
            "args": [
                "--build", "build",
                "-j", "4"
            ],
            "group": {
                "kind": "build",
                "isDefault": true
            },
            "problemMatcher": [
                "$gcc"
            ],
            "options": {
                "cwd": "${workspaceFolder}"
            },
            "dependsOn": [
                "CMake Configure"
            ]
        },
        {
            "label": "Clean",
            "type": "shell",
            "command": "cmake",
            "args": [
                "--build", "build",
                "--target", "clean"
            ],
            "group": "build",
            "problemMatcher": []
        },
        {
            "label": "⚙️ 打开 TI SysConfig",
            "detail": "Launch TI SysConfig GUI to edit pin/peripheral configuration",
            "type": "shell",
            "command": "___SYSCONFIG_NW___",
            "args": [
                "--disable-gpu",
                "___SYSCONFIG_APP___",
                "--script", "___SYSCFG_FILE___"
            ],
            "options": {
                "cwd": "${workspaceFolder}"
            },
            "problemMatcher": [],
            "presentation": {
                "reveal": "silent",
                "panel": "shared"
            }
        },
        {
            "label": "Flash MSPM0",
            "detail": "Flash firmware to device without entering debug mode",
            "type": "shell",
            "command": "___OPENOCD_EXE___",
            "args": [
                "-s", "___OPENOCD_SCRIPTS___",
                "-f", "___FLASH_INTERFACE___",
                "-f", "target/ti_mspm0.cfg",
                "-c", "program build/___PROJECT_NAME___.elf verify reset exit"
            ],
            "options": {
                "cwd": "${workspaceFolder}"
            },
            "problemMatcher": [],
            "presentation": {
                "reveal": "always",
                "panel": "shared"
            }
        }
    ]
}"""

VSCode_SETTINGS_TEMPLATE = """\
{
    "VsCodeTaskButtons.tasks": [
        {
            "label": "$(symbol-misc) SysConfig",
            "task": "⚙️ 打开 TI SysConfig",
            "tooltip": "打开 TI SysConfig 图形化配置界面"
        },
        {
            "label": "$(play) Build",
            "task": "Build MSPM0 project",
            "tooltip": "编译 MSPM0 项目 (cmake --build)"
        },
        {
            "label": "$(zap) Flash",
            "task": "Flash MSPM0",
            "tooltip": "烧录固件到芯片 (不进入调试模式)"
        },
        {
            "label": "$(trash) Clean",
            "task": "Clean",
            "tooltip": "清理构建产物"
        }
    ]
}"""

# =============================================================================
# Step 8b: Template - .vscode/launch.json
# =============================================================================
LAUNCH_JSON_TEMPLATE = """\
{{
    "version": "0.2.0",
    "configurations": [
        {{
            "name": "{device_name} Debug ({debugger_label})",
            "cwd": "${{workspaceFolder}}",
            "executable": "${{workspaceFolder}}/build/{project_name}.elf",
            "request": "launch",
            "type": "cortex-debug",
            "runToEntryPoint": "main",
            "servertype": "openocd",
            "configFiles": [
                {config_files}
            ],
            "openOCDPreConfigLaunchCommands": [
                "set WORKAREASIZE 0x2000"
            ],
            "searchDir": [
                "{openocd_scripts}"
            ],
            "serverpath": "{openocd_bin}",
            "gdbPath": "{gdb_path}"
        }}
    ]
}}"""


# =============================================================================
# Step 8c: Template - .vscode/c_cpp_properties.json
# =============================================================================
CPP_PROPERTIES_TEMPLATE = """\
{{
    "configurations": [
        {{
            "name": "{device_name} ARM GCC",
            "compilerPath": "{compiler_path}",
            "compilerArgs": [
                "-mcpu={cpu}",
                "-mthumb",
                "-std=gnu11"
            ],
            "includePath": [
                "${{workspaceFolder}}/**",
                "${{workspaceFolder}}/config",
                "${{workspaceFolder}}/inc",
                "${{workspaceFolder}}/inc/app",
                "${{workspaceFolder}}/inc/driver",
                "${{workspaceFolder}}/inc/modules",
                "${{workspaceFolder}}/inc/utils",
                "{sdk_dir}/source",
                "{sdk_dir}/source/third_party/CMSIS/Core/Include"
            ],
            "defines": [
                {defines_json}
            ],
            "intelliSenseMode": "linux-gcc-arm",
            "cStandard": "gnu11",
            "cppStandard": "gnu++14"
        }}
    ],
    "version": 4
}}"""


# =============================================================================
# Template generation functions
# =============================================================================
def write_cmake_lists(project_dir: str, ctx: dict, dry_run: bool = False):
    """Generate CMakeLists.txt."""
    # Build complete compile-time defines:
    #   __MSPM0G3507__     — device identifier (required by SDK headers)
    #   __USE_SYSCONFIG__  — SysConfig compatibility marker
    #   CONFIG_MSPM0G350X / CONFIG_MSPM0G3507 — skip: already #define'd in ti_msp_dl_config.h
    defines = [ctx["device_define"], "__USE_SYSCONFIG__"]
    content = CMAKE_TEMPLATE.format(
        project_name=ctx["project_name"],
        sdk_dir=_posix_path(ctx["sdk_dir"]),
        cpu=ctx["cpu"],
        defines_str=" ".join(defines),
        driverlib_path=_posix_path(ctx["driverlib"]),
        startup_path=_posix_path(ctx["startup"]),
    )

    dest = os.path.join(project_dir, "CMakeLists.txt")
    if dry_run:
        info(f"[dry-run] Write CMakeLists.txt ({len(content)} bytes)")
        return
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    info("  ✓ CMakeLists.txt")


def write_main_c(project_dir: str, ctx: dict, dry_run: bool = False):
    """Generate src/main.c."""
    dest = os.path.join(project_dir, "src", "main.c")
    if dry_run:
        info(f"[dry-run] Write src/main.c")
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(MAIN_C_TEMPLATE)
    info("  ✓ src/main.c")


def write_main_h(project_dir: str, ctx: dict, dry_run: bool = False):
    """Generate inc/main.h."""
    content = MAIN_H_TEMPLATE.format(project_name=ctx["project_name"])
    dest = os.path.join(project_dir, "inc", "main.h")
    if dry_run:
        info(f"[dry-run] Write inc/main.h")
        return
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    info("  ✓ inc/main.h")


def write_tasks_json(project_dir: str, sysconfig_cli: str = "", syscfg_name: str = "",
                     openocd_exe: str = "openocd", openocd_scripts: str = "",
                     debugger: str = "cmsis-dap", project_name: str = "",
                     dry_run: bool = False):
    """Generate .vscode/tasks.json."""
    dest = os.path.join(project_dir, ".vscode", "tasks.json")
    if dry_run:
        info(f"[dry-run] Write .vscode/tasks.json")
        return
    sysconfig_dir = os.path.dirname(sysconfig_cli)
    nw_bin = os.path.join(sysconfig_dir, "nw", _SYSCONFIG_NW_NAME)
    app_dir = os.path.join(sysconfig_dir, "app")
    flash_interface = {
        "cmsis-dap": "interface/cmsis-dap.cfg",
        "xds110": "interface/xds110.cfg",
        "jlink": "interface/jlink.cfg",
    }.get(debugger, "interface/cmsis-dap.cfg")
    content = TASKS_JSON_TEMPLATE.replace("___CMAKE_GENERATOR___", _CMAKE_GENERATOR)
    content = content.replace("___SYSCONFIG_NW___", nw_bin)
    content = content.replace("___SYSCONFIG_APP___", app_dir)
    content = content.replace("___SYSCFG_FILE___", syscfg_name)
    content = content.replace("___OPENOCD_EXE___", openocd_exe)
    content = content.replace("___OPENOCD_SCRIPTS___", openocd_scripts)
    content = content.replace("___FLASH_INTERFACE___", flash_interface)
    content = content.replace("___PROJECT_NAME___", project_name)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    info("  ✓ .vscode/tasks.json")


def write_launch_json(project_dir: str, ctx: dict, dry_run: bool = False):
    """Generate .vscode/launch.json."""
    debugger = ctx["debugger"]
    if debugger == "none":
        info("  - Skip launch.json (debugger=none)")
        return

    dbg_cfg = DEBUGGER_CONFIG[debugger]
    config_files = ",\n                ".join(
        f'"{f}"' for f in dbg_cfg["configFiles"]
    )
    debugger_label = {"cmsis-dap": "CMSIS-DAP", "xds110": "XDS110", "jlink": "JLink"}.get(debugger, debugger.upper())

    openocd_bin = _posix_path(ctx["openocd_exe"])
    openocd_scripts = _posix_path(ctx.get("openocd_scripts", ""))
    gdb_path = _posix_path(ctx["gdb_exe"])

    content = LAUNCH_JSON_TEMPLATE.format(
        device_name=ctx["device_name"],
        debugger_label=debugger_label,
        project_name=ctx["project_name"],
        config_files=config_files,
        openocd_scripts=openocd_scripts,
        openocd_bin=openocd_bin,
        gdb_path=gdb_path,
    )

    dest = os.path.join(project_dir, ".vscode", "launch.json")
    if dry_run:
        info(f"[dry-run] Write .vscode/launch.json")
        return
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    info("  ✓ .vscode/launch.json")


def write_cpp_properties(project_dir: str, ctx: dict, dry_run: bool = False):
    """Generate .vscode/c_cpp_properties.json."""
    defines = [ctx["device_define"], "__USE_SYSCONFIG__"]
    defines_json = ",\n                ".join(f'"{d}"' for d in defines)
    gcc_path = shutil.which("arm-none-eabi-gcc") or "/usr/bin/arm-none-eabi-gcc"

    content = CPP_PROPERTIES_TEMPLATE.format(
        device_name=ctx["device_name"],
        cpu=ctx["cpu"],
        sdk_dir=_posix_path(ctx["sdk_dir"]),
        defines_json=defines_json,
        compiler_path=_posix_path(gcc_path),
    )

    dest = os.path.join(project_dir, ".vscode", "c_cpp_properties.json")
    if dry_run:
        info(f"[dry-run] Write .vscode/c_cpp_properties.json")
        return
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    info("  ✓ .vscode/c_cpp_properties.json")


def write_vscode_settings(project_dir: str, dry_run: bool = False):
    """Generate .vscode/settings.json with Task Buttons config for status-bar buttons."""
    dest = os.path.join(project_dir, ".vscode", "settings.json")
    if dry_run:
        info("[dry-run] Write .vscode/settings.json (Task Buttons)")
        return

    # Merge with existing settings if present
    existing = {}
    if os.path.isfile(dest):
        try:
            with open(dest, "r") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, ValueError):
            pass

    tb_config = json.loads(VSCode_SETTINGS_TEMPLATE)
    existing.update(tb_config)

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=4, ensure_ascii=False)
        f.write("\n")
    info("  ✓ .vscode/settings.json (Task Buttons)")


# =============================================================================
# Step 9: CMake configure + build
# =============================================================================
def run_cmake_build(project_dir: str, dry_run: bool = False) -> bool:
    """Run cmake configure + build."""
    build_dir = os.path.join(project_dir, "build")
    
    cached_generator = _cmake_cached_generator(build_dir)
    if cached_generator and cached_generator != _CMAKE_GENERATOR:
        warn(
            f"Existing build cache uses {cached_generator}; rebuilding {build_dir} for {_CMAKE_GENERATOR}"
        )
        if dry_run:
            info("[dry-run] Skip build directory reset")
        else:
            shutil.rmtree(build_dir)

    # Configure
    configure_cmd = [
        "cmake", "-B", build_dir,
        "-G", _CMAKE_GENERATOR,
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ".",
    ]
    info(f"cmake configure: {' '.join(configure_cmd)}")

    if dry_run:
        info("[dry-run] Skip cmake configure")
        return True

    result = subprocess.run(
        configure_cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error(f"cmake configure failed:\n{result.stderr}\n{result.stdout}")
        return False
    success("cmake configure succeeded")

    # Build
    import multiprocessing
    jobs = multiprocessing.cpu_count()
    build_cmd = ["cmake", "--build", build_dir, "-j", str(jobs)]
    info(f"cmake build: {' '.join(build_cmd)}")

    result = subprocess.run(
        build_cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error(f"cmake build failed:\n{result.stderr}")
        # Show last few lines of stdout
        stdout_lines = result.stdout.strip().split("\n")
        for line in stdout_lines[-10:]:
            error(f"  {line}")
        return False
    success("cmake build succeeded")
    return True


# =============================================================================
# Helper: copy syscfg to project dir
# =============================================================================
def copy_syscfg(syscfg_path: str, project_dir: str, dry_run: bool = False):
    """Copy user's original .syscfg to project root."""
    if not syscfg_path or not os.path.isfile(syscfg_path):
        return
    dest = os.path.join(project_dir, os.path.basename(syscfg_path))
    # Skip when source and dest are the same file (in-place project creation)
    if os.path.abspath(syscfg_path) == os.path.abspath(dest):
        info("  - syscfg already at project root, skipping copy")
        return
    if dry_run:
        info(f"[dry-run] cp {syscfg_path} → {dest}")
        return
    shutil.copy2(syscfg_path, dest)
    info("  \u2713 syscfg copied")


# =============================================================================
# Print project summary
# =============================================================================
def print_summary(ctx: dict):
    """Print project creation summary."""
    pin_groups = ctx.get("pin_groups", [])
    pin_summary = ""
    for grp in pin_groups:
        pins = ", ".join(f"{p['name']}({p.get('iomux', p['define'])})" for p in grp["pins"])
        pin_summary += f"\n          {grp['name']} @ {grp['port']}: [{pins}]"

    print(f"""
{Color.BOLD}{Color.GREEN}╔══════════════════════════════════════════════════╗
║   MSPM0 project "{ctx['project_name']}" ready   ║
╚══════════════════════════════════════════════════╝{Color.RESET}

  📁 Path:      {ctx['project_dir']}
  🔧 Chip:      {ctx['device_name']} ({ctx['cpu'].upper()} @ {ctx['cpu_freq_hz']//1_000_000}MHz)
  📦 Flash:    {ctx['flash_kb']}KB / SRAM: {ctx['sram_kb']}KB
  🐞 Debugger:   {ctx['debugger'].upper()}{pin_summary}

  Build:
    cd {ctx['project_dir']}
    cmake -B build -G {_CMAKE_GENERATOR} -DCMAKE_EXPORT_COMPILE_COMMANDS=ON .
    cmake --build build -j$(nproc)

  Flash (OpenOCD):
    openocd -f interface/{ctx['debugger']}.cfg -f target/ti_mspm0.cfg \\
      -c "program build/{ctx['project_name']}.elf verify reset exit"
""")


# =============================================================================
# cmd_new() — Create a new project
# =============================================================================
def cmd_new(args):
    print(f"\n{Color.BOLD}{Color.CYAN}╔════════════════════════════════════╗")
    print(f"║   MSPM0 Project Init v0.1.0       ║")
    print(f"╚════════════════════════════════════╝{Color.RESET}\n")

    # ── Step 1: Auto-discover syscfg if not provided ──
    info("--- Step 1: Locate configuration ---")
    device = args.device
    package = args.package

    if not args.syscfg:
        cwd_syscfg = sorted(Path(os.getcwd()).glob("*.syscfg"))
        if len(cwd_syscfg) == 1:
            args.syscfg = str(cwd_syscfg[0])
            info(f"Auto-discovered: {os.path.basename(args.syscfg)}")
        elif len(cwd_syscfg) > 1:
            warn(f"Multiple .syscfg files found in current directory:")
            for i, f in enumerate(cwd_syscfg, 1):
                print(f"    {i}. {f.name}")
            choice = input("  Select number (or Enter to skip): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(cwd_syscfg):
                args.syscfg = str(cwd_syscfg[int(choice) - 1])
                info(f"Using: {os.path.basename(args.syscfg)}")
            else:
                warn("No selection made, proceeding without syscfg")
        else:
            info("No .syscfg found in current directory (use --device for manual setup)")

    if args.syscfg:
        meta = parse_syscfg_metadata(args.syscfg)
        device = device or meta["device"]
        package = package or meta["package"]
        info(f"Device: {device}, Package: {package}")

    # ── Step 2: Validate environment ──
    info("--- Step 2: Validate environment ---")
    if not validate_environment(args):
        sys.exit(1)

    # ── Determine output directory ──
    project_dir = args.output or os.path.join(os.getcwd(), args.name)
    project_dir = os.path.abspath(project_dir)

    if os.path.exists(project_dir) and os.listdir(project_dir):
        # Skip warning when only .syscfg files and hidden artifacts exist
        # (e.g. in-place init where the .syscfg IS the only content)
        contents = os.listdir(project_dir)
        ignorable = {f for f in contents
                     if f.endswith(".syscfg") or f == ".sysconfig_backup"
                     or f.startswith(".")}
        if set(contents) - ignorable:
            warn(f"Target directory not empty: {project_dir}")
            ans = input("  Continue? Existing files may be overwritten [y/N]: ")
            if ans.lower() != "y":
                info("Cancelled")
                sys.exit(0)
        else:
            info(f"Directory has only .syscfg — creating project in-place")

    if not device:
        error("Cannot determine chip model. Provide .syscfg or --device")
        sys.exit(1)
    if not package:
        chip_tmp = resolve_chip(device, args.sdk)
        pkgs = chip_tmp.get("package_options", [])
        package = pkgs[0] if pkgs else "Default"
        warn(f"No package specified, using default: {package}")

    # ── Step 3: Invoke SysConfig CLI ──
    sysconfig_tmp = os.path.join(project_dir, ".sysconfig_tmp")
    if args.syscfg:
        info("--- Step 3: SysConfig CLI code generation ---")
        if not run_sysconfig(
            args.syscfg, sysconfig_tmp,
            device, package,
            args.sdk, args._sysconfig_cli,
            args.dry_run,
        ):
            sys.exit(1)
    else:
        info("--- Step 3: Skip (no syscfg) ---")
        os.makedirs(sysconfig_tmp, exist_ok=True)

    # Ensure ti_msp_dl_config.c/h exist (generate stubs if SysConfig skipped them)
    if not args.dry_run:
        write_dl_config_stubs(sysconfig_tmp, device or args.device or "MSPM0G3507", args.sdk, args.dry_run)

    # -- Step 4: Parse generated headers --
    info("--- Step 4: Parse metadata ---")
    dl_config_h = os.path.join(sysconfig_tmp, "ti_msp_dl_config.h")
    dl_meta = parse_dl_config(dl_config_h)

    chip = resolve_chip(device, args.sdk)
    info(f"Chip: {chip['device_name']}, CPU: {chip['cpu']}, "
         f"Flash: {chip['flash_kb']}KB, SRAM: {chip['sram_kb']}KB")
    if dl_meta["pin_groups"]:
        info(f"Pin groups: {len(dl_meta['pin_groups'])}, "
             f"CPU frequency: {dl_meta['cpu_freq_hz']}Hz")

    # ── Build context ──
    ctx = _build_ctx(args, project_dir, chip, dl_meta)

    # -- Step 5: Create directories --
    info("--- Step 5: Create directory structure ---")
    create_directories(project_dir, args.dry_run)

    # -- Step 6: Distribute files --
    info("--- Step 6: Distribute generated files ---")
    distribute_files(sysconfig_tmp, project_dir, args.dry_run)
    copy_syscfg(args.syscfg, project_dir, args.dry_run)

    # -- Step 7: Write templates --
    info("--- Step 7: Generate code templates ---")
    write_cmake_lists(project_dir, ctx, args.dry_run)
    write_main_c(project_dir, ctx, args.dry_run)
    write_main_h(project_dir, ctx, args.dry_run)

    # -- Step 8: Write .vscode configs --
    info("--- Step 8: Generate VSCode configs ---")
    write_tasks_json(project_dir,
                     sysconfig_cli=args._sysconfig_cli,
                     syscfg_name=os.path.basename(args.syscfg) if args.syscfg else f"{args.name}.syscfg",
                     openocd_exe=ctx["openocd_exe"],
                     openocd_scripts=ctx["openocd_scripts"],
                     debugger=ctx["debugger"],
                     project_name=ctx["project_name"],
                     dry_run=args.dry_run)
    write_launch_json(project_dir, ctx, args.dry_run)
    write_cpp_properties(project_dir, ctx, args.dry_run)
    write_vscode_settings(project_dir, args.dry_run)

    # ── Clean up temp directory ──
    if not args.dry_run and os.path.isdir(sysconfig_tmp):
        shutil.rmtree(sysconfig_tmp)

    # ── Step 9: cmake build ──
    if not args.dry_run and not args.no_build and args.syscfg:
        info("--- Step 9: CMake build verification ---")
        run_cmake_build(project_dir, args.dry_run)
    elif args.dry_run:
        info("--- Step 9: [dry-run] Skip build ---")

    # ── Step 10: Git init ──
    if not args.no_git:
        if has_git():
            if not args.dry_run:
                init_git(project_dir, args.dry_run)
            else:
                info("[dry-run] git init + .gitignore")
        else:
            info("Git not found — 未启用版本控制，可安装 git 后在项目目录手动 git init")

    # -- Summary --
    print_summary(ctx)


# =============================================================================
# cmd_regenerate() — Re-run SysConfig for an existing project
# =============================================================================
def cmd_regenerate(args):
    project_dir = os.path.abspath(args.project_dir)

    print(f"\n{Color.BOLD}{Color.CYAN}╔════════════════════════════════════╗")
    print(f"║   MSPM0 Regenerate SysConfig       ║")
    print(f"╚════════════════════════════════════╝{Color.RESET}\n")

    # ---- Validate project directory ----
    if not os.path.isdir(project_dir):
        error(f"Project directory not found: {project_dir}")
        sys.exit(1)

    # Find .syscfg file
    syscfg_files = sorted(Path(project_dir).glob("*.syscfg"))
    if not syscfg_files:
        error(f"No .syscfg file found in {project_dir}")
        error("Run 'mspm0-init new' to create a project first, or place a .syscfg file in the project root")
        sys.exit(1)

    syscfg_path = str(syscfg_files[0])
    if len(syscfg_files) > 1:
        warn(f"Multiple .syscfg files found, using: {os.path.basename(syscfg_path)}")

    info(f"Project:  {project_dir}")
    info(f"SysConfig: {syscfg_path}")

    # ---- Validate env ----
    info("--- Validate environment ---")
    sysconfig_cli = os.path.join(args.sysconfig, _SYSCONFIG_CLI_NAME)
    if not os.path.isfile(sysconfig_cli):
        error(f"SysConfig CLI not found: {sysconfig_cli}")
        sys.exit(1)

    product_json = os.path.join(args.sdk, ".metadata", "product.json")
    if not os.path.isfile(product_json):
        error(f"MSPM0 SDK not found: {args.sdk}")
        sys.exit(1)

    success("Environment OK")

    # ---- Parse syscfg for device/package ----
    meta = parse_syscfg_metadata(syscfg_path)
    device = meta["device"]
    package = meta["package"]
    if not device:
        error("Cannot determine device from .syscfg. The file may be incomplete.")
        sys.exit(1)
    info(f"Device: {device}, Package: {package}")

    # ---- Backup existing generated files ----
    GENERATED_FILES = [
        "config/ti_msp_dl_config.h",
        "config/ti_msp_dl_config.c",
        "config/device_linker.lds",
        "config/device.opt",
    ]

    if args.backup and not args.dry_run:
        backup_dir = os.path.join(project_dir, ".sysconfig_backup")
        os.makedirs(backup_dir, exist_ok=True)
        for f in GENERATED_FILES:
            src = os.path.join(project_dir, f)
            if os.path.isfile(src):
                dst = os.path.join(backup_dir, f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        info(f"Backed up to {backup_dir}/")

    # ---- Run SysConfig CLI ----
    info("--- SysConfig CLI ---")
    tmp_out = os.path.join(project_dir, ".sysconfig_tmp")
    if not args.dry_run and os.path.isdir(tmp_out):
        shutil.rmtree(tmp_out)

    if not run_sysconfig(
        syscfg_path, tmp_out,
        device, package or "Default",
        args.sdk, sysconfig_cli,
        args.dry_run,
    ):
        error("SysConfig CLI failed. Old files have NOT been modified.")
        if args.backup:
            info(f"Restore from backup: {os.path.join(project_dir, '.sysconfig_backup')}")
        sys.exit(1)

    # ---- Copy new files into project ----
    info("--- Updating project files ---")
    updated = []
    for f in GENERATED_FILES:
        basename = os.path.basename(f)
        src = os.path.join(tmp_out, basename)
        dst = os.path.join(project_dir, f)
        if os.path.isfile(src):
            if args.dry_run:
                info(f"  [dry-run] {f} -> {dst}")
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            updated.append(f)

    # Also update excluded files
    EXCLUDED_FILES = ["device_linker.cmd", "device.cmd.genlibs", "device.lds.genlibs", "Event.dot"]
    for f in EXCLUDED_FILES:
        src = os.path.join(tmp_out, "excluded", f)
        dst_dir = os.path.join(project_dir, "excluded")
        dst = os.path.join(dst_dir, f)
        if os.path.isfile(src):
            if args.dry_run:
                info(f"  [dry-run] excluded/{f}")
            else:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src, dst)
                updated.append(f"excluded/{f}")

    # Clean tmp
    if not args.dry_run and os.path.isdir(tmp_out):
        shutil.rmtree(tmp_out)

    success(f"Updated {len(updated)} file(s): {', '.join(updated)}")

    # ---- Parse new metadata ----
    dl_config_h = os.path.join(project_dir, "config", "ti_msp_dl_config.h")
    dl_meta = parse_dl_config(dl_config_h)
    chip = resolve_chip(device, args.sdk)

    if dl_meta["pin_groups"]:
        info(f"Pin groups: {len(dl_meta['pin_groups'])}, CPU: {dl_meta['cpu_freq_hz']}Hz")
        for grp in dl_meta["pin_groups"]:
            pins = ", ".join(p["name"] for p in grp["pins"])
            info(f"  {grp['name']} @ {grp['port']}: [{pins}]")

    # ---- Rebuild ----
    if not args.dry_run and not args.no_build:
        info("--- Rebuilding ---")
        run_cmake_build(project_dir, args.dry_run)

    # ---- Regenerate VSCode configs (paths may have changed) ----
    if args.debugger != "none":
        info("--- Updating VSCode configs ---")
        project_name = os.path.basename(project_dir)
        openocd_exe = _resolve_openocd_exe(args.openocd)
        gdb_exe = _resolve_gdb_exe(args.gdb)
        vscode_ctx = {
            "project_name": project_name,
            "project_dir": project_dir,
            "sdk_dir": args.sdk,
            "debugger": args.debugger,
            "openocd_exe": openocd_exe,
            "openocd_scripts": _resolve_openocd_scripts(openocd_exe),
            "gdb_exe": gdb_exe,
            "cpu": chip["cpu"],
            "device_name": chip["device_name"],
            "device_define": chip["device_define"],
        }
        write_tasks_json(project_dir,
                         sysconfig_cli=sysconfig_cli,
                         syscfg_name=os.path.basename(syscfg_path),
                         openocd_exe=openocd_exe,
                         openocd_scripts=_resolve_openocd_scripts(openocd_exe),
                         debugger=args.debugger,
                         project_name=project_name,
                         dry_run=args.dry_run)
        write_launch_json(project_dir, vscode_ctx, args.dry_run)
        write_cpp_properties(project_dir, vscode_ctx, args.dry_run)

    # ---- Update VSCode settings (Task Buttons, etc.) ----
    write_vscode_settings(project_dir, args.dry_run)

    # ---- Git init (if not already a repo) ----
    if not args.no_git and not os.path.isdir(os.path.join(project_dir, ".git")):
        if has_git():
            if not args.dry_run:
                init_git(project_dir, args.dry_run)
            else:
                info("[dry-run] git init + .gitignore")
        else:
            info("Git not found — 未启用版本控制")

    print(f"""
{Color.BOLD}{Color.GREEN}  Regeneration complete.{Color.RESET}
  Project: {project_dir}
  Chip:    {chip.get('device_name', device)}
""")


# =============================================================================
# _build_ctx() — shared context builder
# =============================================================================
def _build_ctx(args, project_dir, chip, dl_meta):
    openocd_exe = _resolve_openocd_exe(args.openocd)
    gdb_exe = _resolve_gdb_exe(args.gdb)
    return {
        "project_name": args.name,
        "project_dir": project_dir,
        "sdk_dir": args.sdk,
        "sysconfig_dir": args.sysconfig,
        "debugger": args.debugger,
        "openocd_exe": openocd_exe,
        "openocd_scripts": _resolve_openocd_scripts(openocd_exe),
        "gdb_exe": gdb_exe,
        "cpu": chip["cpu"],
        "startup": chip["startup"],
        "driverlib": chip["driverlib"],
        "flash_kb": chip["flash_kb"],
        "sram_kb": chip["sram_kb"],
        "device_name": chip["device_name"],
        "device_define": chip["device_define"],
        "chip_defines": dl_meta["chip_defines"],
        "cpu_freq_hz": dl_meta["cpu_freq_hz"],
        "pin_groups": dl_meta["pin_groups"],
    }


# =============================================================================
# main() — dispatch
# =============================================================================
def main():
    # Backward compat: if first arg is not a subcommand, insert 'new'
    _args = sys.argv[1:]
    if _args and _args[0] not in ("new", "regenerate", "check", "-h", "--help", "--check"):
        # Check if it looks like a path or is an option flag
        if not _args[0].startswith("-"):
            sys.argv.insert(1, "new")
        elif "-n" in _args or "--name" in _args:
            sys.argv.insert(1, "new")

    args = parse_args()

    if args.command == "regenerate":
        cmd_regenerate(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "new" or hasattr(args, "name"):
        cmd_new(args)
    elif args.check:
        cmd_check(args)
    elif args.command is None:
        # No subcommand — intelligently detect context
        cwd = Path.cwd()
        has_syscfg = list(cwd.glob("*.syscfg"))
        has_cmake = (cwd / "CMakeLists.txt").exists()

        if has_cmake and has_syscfg:
            # Looks like an existing project — regenerate
            info("Detected existing project — auto-regenerating")
            sys.argv = [sys.argv[0], "regenerate", str(cwd)]
            cmd_regenerate(parse_args())
        elif has_syscfg:
            # Clean dir with .syscfg — use its name as project name, init here
            name = has_syscfg[0].stem
            info(f"Auto-detected: {has_syscfg[0].name} → project '{name}'")
            sys.argv = [sys.argv[0], "new", str(has_syscfg[0]), "-n", name, "-o", str(cwd)]
            cmd_new(parse_args())
        else:
            print("\n用法: mspm0-init [子命令] [选项]")
            print()
            print("子命令:")
            print("  new          创建新项目")
            print("  regenerate   重新生成 SysConfig 配置")
            print("  check        环境自检")
            print()
            print("快速开始:")
            print("  mspm0-init                         (自动检测当前目录)")
            print("  mspm0-init new -n my_project       (自动发现 .syscfg)")
            print("  mspm0-init regenerate              (项目内重生成)")
            print()
            print("完整教程: mspm0-init --help")
            sys.exit(0)


if __name__ == "__main__":
    main()
