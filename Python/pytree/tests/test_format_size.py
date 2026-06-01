from pytree_lib.models import format_size


def test_format_size_bytes():
    assert format_size(512) == "512.0 B"


def test_format_size_mb():
    assert "MB" in format_size(5 * 1024 * 1024)
