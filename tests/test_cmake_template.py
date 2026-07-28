from ti_project_assistant.cli import CMAKE_TEMPLATE


def _render_cmake_template() -> str:
    return CMAKE_TEMPLATE.format(
        project_name="template_test",
        sdk_dir="C:/ti/mspm0_sdk",
        cpu="cortex-m0plus",
        defines_str="__MSPM0G3507__ __USE_SYSCONFIG__",
        driverlib_path="ti/driverlib/lib/gcc/m0p/mspm0g1x0x_g3x0x.a",
        startup_path="ti/devices/msp/m0p/startup_system_files/gcc/startup_mspm0g350x_gcc.c",
    )


def test_compilers_are_selected_before_project_enables_languages():
    cmake = _render_cmake_template()
    project_position = cmake.index("project(template_test C ASM)")

    for setting in (
        "set(CMAKE_C_COMPILER   arm-none-eabi-gcc)",
        "set(CMAKE_CXX_COMPILER arm-none-eabi-g++)",
        "set(CMAKE_ASM_COMPILER arm-none-eabi-gcc)",
    ):
        assert cmake.index(setting) < project_position


def test_try_compile_target_type_is_selected_before_project():
    cmake = _render_cmake_template()

    assert (
        cmake.index("set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)")
        < cmake.index("project(template_test C ASM)")
    )
