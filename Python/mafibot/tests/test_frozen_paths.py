"""Bundled asset paths (dev install mirrors PyInstaller layout under bundle_root)."""

from __future__ import annotations

from mafibot._frozen import bundle_root


def test_bundle_root_contains_ui_and_default_profiles() -> None:
    root = bundle_root()
    assert (root / "static" / "index.html").is_file()
    assert any((root / "profiles").glob("*.json"))
