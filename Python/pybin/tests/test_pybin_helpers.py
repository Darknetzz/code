"""Unit tests for pybin pure helpers (no PyInstaller runs)."""
import importlib.util
import sys
from pathlib import Path

import pytest

_PYBIN_DIR = Path(__file__).resolve().parents[1]
_PYBIN_PATH = _PYBIN_DIR / "pybin.py"


def _load_pybin():
    spec = importlib.util.spec_from_file_location("pybin_under_test", _PYBIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["pybin_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pybin():
    return _load_pybin()


def test_normalize_exe_basename(pybin):
    assert pybin._normalize_exe_basename("tool.exe") == "tool"
    assert pybin._normalize_exe_basename("tool") == "tool"
    assert pybin._normalize_exe_basename("Tool.EXE") == "Tool"


def test_has_glob(pybin):
    assert pybin._has_glob("*.py") is True
    assert pybin._has_glob("script.py") is False


def test_matches_any_pattern(pybin):
    path = Path("src/_helper.py")
    assert pybin._matches_any_pattern(path, ["_*"]) is True
    assert pybin._matches_any_pattern(path, ["*.txt"]) is False


def test_expand_inputs_skips_underscore_when_multi(pybin, tmp_path):
    a = tmp_path / "main.py"
    b = tmp_path / "_core.py"
    a.write_text("print(1)\n", encoding="utf-8")
    b.write_text("x = 1\n", encoding="utf-8")
    out = pybin._expand_inputs([a, b], excludes=[], include_underscore=False)
    assert out == [a]


def test_expand_inputs_include_underscore(pybin, tmp_path):
    a = tmp_path / "main.py"
    b = tmp_path / "_core.py"
    a.write_text("print(1)\n", encoding="utf-8")
    b.write_text("x = 1\n", encoding="utf-8")
    out = pybin._expand_inputs([a, b], excludes=[], include_underscore=True)
    assert len(out) == 2


def test_spec_looks_compatible_relative(pybin, tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("print('hi')\n", encoding="utf-8")
    spec = tmp_path / "hello.spec"
    spec.write_text(
        "a = Analysis(['hello.py'], pathex=[], binaries=[], datas=[], hiddenimports=[], "
        "hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)\n",
        encoding="utf-8",
    )
    ok, reason = pybin._spec_looks_compatible(spec, script)
    assert ok, reason


def test_spec_looks_compatible_rejects_absolute(pybin, tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("print('hi')\n", encoding="utf-8")
    spec = tmp_path / "hello.spec"
    spec.write_text(
        "a = Analysis(['D:\\\\foo\\\\hello.py'], pathex=[], binaries=[], datas=[], "
        "hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], "
        "noarchive=False)\n",
        encoding="utf-8",
    )
    ok, reason = pybin._spec_looks_compatible(spec, script)
    assert not ok
    assert "absolute" in reason.lower()


def test_patch_regenerated_spec(pybin, tmp_path):
    spec = tmp_path / "app.spec"
    spec.write_text(
        "a = Analysis(['D:\\\\old\\\\app.py'], pathex=[], binaries=[], datas=[], "
        "hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], "
        "noarchive=False)\n",
        encoding="utf-8",
    )
    pybin._patch_regenerated_spec(spec, entry_basename="app.py", ensure_rich=False)
    text = spec.read_text(encoding="utf-8")
    assert "['app.py']" in text
    assert "D:\\\\old" not in text


def test_script_imports_rich(pybin, tmp_path):
    rich_script = tmp_path / "r.py"
    rich_script.write_text("from rich.console import Console\n", encoding="utf-8")
    plain = tmp_path / "p.py"
    plain.write_text("print(1)\n", encoding="utf-8")
    assert pybin._script_imports_rich(rich_script) is True
    assert pybin._script_imports_rich(plain) is False
