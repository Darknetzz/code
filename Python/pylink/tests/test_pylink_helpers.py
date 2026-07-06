"""Unit tests for pylink pure helpers."""
import importlib.util
import sys
from pathlib import Path as PathLib

import pytest

_PYLINK_PATH = PathLib(__file__).resolve().parents[1] / "pylink.py"


def _load_pylink():
    spec = importlib.util.spec_from_file_location("pylink_under_test", _PYLINK_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["pylink_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pylink():
    return _load_pylink()


def test_is_drive_root(pylink):
    assert pylink.is_drive_root(PathLib("D:\\")) is True
    assert pylink.is_drive_root(PathLib("D:\\folder")) is False


def test_normalize_absolute_path(pylink, tmp_path):
    p = pylink.normalize_absolute_path(PathLib(tmp_path / "sub"))
    assert p.is_absolute()


def test_validate_link_flags_exclusive(pylink):
    err = pylink.validate_link_flags(directory=True, junction=True, hard=False)
    assert err is not None
    assert pylink.validate_link_flags(directory=False, junction=False, hard=False) is None


def test_resolve_default_directory_flag_yes(pylink):
    assert pylink.resolve_default_directory_flag(yes=True) == "/J"


def test_format_link_display(pylink):
    link = PathLib("D:\\link")
    target = PathLib("C:\\target")
    assert pylink.format_link_display(link, target) == "D:\\link -> C:\\target"


def test_format_link_type(pylink):
    assert pylink.format_link_type("/J") == "/J (directory junction)"
    assert pylink.format_link_type("/D") == "/D (directory symbolic link)"
    assert pylink.format_link_type("/H") == "/H (hard link, same volume, files only)"
    assert pylink.format_link_type("") == "file symbolic link"
    assert pylink.format_link_type("/X") == "/X"
