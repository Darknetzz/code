"""Unit tests for pylink pure helpers."""
import importlib.util
import os
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


def test_validate_relative_flag(pylink):
    assert pylink.validate_relative_flag(relative=True, junction=True, hard=False) is not None
    assert pylink.validate_relative_flag(relative=True, junction=False, hard=True) is not None
    assert pylink.validate_relative_flag(relative=True, junction=False, hard=False) is None
    assert pylink.validate_relative_flag(relative=False, junction=True, hard=False) is None


def test_resolve_default_directory_flag_yes(pylink):
    assert pylink.resolve_default_directory_flag(yes=True) == "/J"


def test_resolve_default_directory_flag_yes_remote(pylink):
    assert pylink.resolve_default_directory_flag(yes=True, remote=True) == "/D"


def test_resolve_default_directory_flag_yes_relative(pylink):
    assert pylink.resolve_default_directory_flag(yes=True, relative_target=True) == "/D"


def test_prefer_directory_symlink(pylink):
    assert pylink.prefer_directory_symlink(relative_target=False, remote=False) is False
    assert pylink.prefer_directory_symlink(relative_target=True, remote=False) is True
    assert pylink.prefer_directory_symlink(relative_target=False, remote=True) is True


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


def test_normalize_cli_argv(pylink):
    assert pylink._normalize_cli_argv(["version"]) == ["version"]
    assert pylink._normalize_cli_argv(["--version"]) == ["version"]
    assert pylink._normalize_cli_argv(["-V"]) == ["version"]
    assert pylink._normalize_cli_argv(["info", "D:\\link"]) == ["info", "D:\\link"]
    assert pylink._normalize_cli_argv(["--help"]) == ["--help"]
    assert pylink._normalize_cli_argv(["C:\\target", "D:\\link"]) == [
        "create-link",
        "C:\\target",
        "D:\\link",
    ]
    assert pylink._normalize_cli_argv(["-y", "C:\\target", "D:\\link"]) == [
        "create-link",
        "-y",
        "C:\\target",
        "D:\\link",
    ]


def test_is_unc_path(pylink):
    assert pylink.is_unc_path(PathLib(r"\\nas3\share\foo")) is True
    assert pylink.is_unc_path(r"//nas3/share/foo") is True
    assert pylink.is_unc_path(r"\\?\UNC\nas3\share\foo") is True
    assert pylink.is_unc_path(PathLib(r"D:\folder")) is False
    assert pylink.is_unc_path(r"\\?\D:\folder") is False


def test_is_remote_path_unc(pylink):
    assert pylink.is_remote_path(PathLib(r"\\nas3\share\foo")) is True


def test_is_remote_path_mapped_drive(pylink):
    assert pylink.is_remote_path(PathLib(r"Z:\Code\Web"), drive_type_fn=lambda _root: 4) is True
    assert pylink.is_remote_path(PathLib(r"D:\local"), drive_type_fn=lambda _root: 3) is False


def test_target_looks_nonportable(pylink):
    assert pylink.target_looks_nonportable(r"Z:\Code\foo") is True
    assert pylink.target_looks_nonportable(r"\\nas3\share\foo") is True
    assert pylink.target_looks_nonportable(r"\??\Z:\Code\foo") is True
    assert pylink.target_looks_nonportable("fullcalendar-7.0.2") is False
    assert pylink.target_looks_nonportable("../other/foo") is False


def test_stored_symlink_target_same_dir(pylink, tmp_path):
    link = tmp_path / "latest"
    stored = pylink.stored_symlink_target(
        "fullcalendar-7.0.2", link, force_relative=False, cwd=tmp_path
    )
    assert stored == "fullcalendar-7.0.2"


def test_stored_symlink_target_trailing_slash_and_dot_prefix(pylink, tmp_path):
    link = tmp_path / "latest"
    stored_slash = pylink.stored_symlink_target(
        "fullcalendar-7.0.2\\", link, force_relative=False, cwd=tmp_path
    )
    stored_dot = pylink.stored_symlink_target(
        ".\\fullcalendar-7.0.2", link, force_relative=False, cwd=tmp_path
    )
    assert stored_slash == "fullcalendar-7.0.2"
    assert stored_dot == "fullcalendar-7.0.2"
    assert not os.path.isabs(stored_slash)
    assert not os.path.isabs(stored_dot)


def test_stored_symlink_target_cwd_differs(pylink, tmp_path):
    link_dir = tmp_path / "fullcalendar"
    link_dir.mkdir()
    link = link_dir / "latest"
    stored = pylink.stored_symlink_target(
        str(PathLib("fullcalendar") / "fullcalendar-7.0.2"),
        link,
        force_relative=False,
        cwd=tmp_path,
    )
    assert stored == "fullcalendar-7.0.2"


def test_stored_symlink_target_absolute_kept(pylink, tmp_path):
    target = tmp_path / "fullcalendar-7.0.2"
    link = tmp_path / "latest"
    stored = pylink.stored_symlink_target(
        str(target), link, force_relative=False, cwd=tmp_path
    )
    assert os.path.isabs(stored)
    assert PathLib(stored) == pylink.resolve_user_target(str(target), cwd=tmp_path)


def test_stored_symlink_target_force_relative(pylink, tmp_path):
    other = tmp_path / "other" / "foo"
    link = tmp_path / "fullcalendar" / "latest"
    stored = pylink.stored_symlink_target(
        str(other), link, force_relative=True, cwd=tmp_path
    )
    assert stored == "../other/foo"
    assert "\\" not in stored


def test_junction_remote_error_message(pylink):
    msg = pylink.junction_remote_error_message(
        PathLib(r"\\nas3\share\latest"),
        PathLib(r"\\nas3\share\fullcalendar-7.0.2"),
    )
    assert msg is not None
    assert "NTFS" in msg


def test_junction_local_no_error(pylink, tmp_path):
    msg = pylink.junction_remote_error_message(
        tmp_path / "latest",
        tmp_path / "target",
        drive_type_fn=lambda _root: 3,
    )
    assert msg is None


def test_posix_ln_suggestion(pylink):
    assert (
        pylink.posix_ln_suggestion("fullcalendar-7.0.2", PathLib(r"Z:\assets\latest"))
        == "ln -s fullcalendar-7.0.2 latest"
    )
