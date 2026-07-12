"""TI Project Assistant — MSPM0 embedded project bootstrap tool."""

# Version is derived from git tags by hatch-vcs at build time.
# Priority: _version.py (in wheel / after build) → package metadata (pip install -e .) → dev fallback
try:
    from ._version import __version__, __version_tuple__
except ImportError:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version
    try:
        __version__ = _pkg_version("ti-project-assistant")
    except PackageNotFoundError:
        __version__ = "0.0.0.dev"
