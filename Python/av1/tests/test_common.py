from common import SUPPORTED_EXTENSIONS, format_duration, format_size


def test_supported_extensions():
    assert ".mp4" in SUPPORTED_EXTENSIONS
    assert ".mkv" in SUPPORTED_EXTENSIONS


def test_format_duration():
    assert format_duration(3661.5).startswith("01:")


def test_format_size_gb():
    assert "GB" in format_size(2 * 1024**3)
