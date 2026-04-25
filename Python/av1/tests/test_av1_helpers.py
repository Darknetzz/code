import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def load_av1_module():
    module_path = Path(__file__).resolve().parents[1] / "av1.py"
    spec = importlib.util.spec_from_file_location("av1_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


av1 = load_av1_module()


def test_normalize_cli_argv_defaults_to_main():
    assert av1._normalize_cli_argv(["av1", "movie.mp4", "--dry-run"]) == [
        "av1",
        "main",
        "movie.mp4",
        "--dry-run",
    ]
    assert av1._normalize_cli_argv(["av1", "clean", "videos"]) == ["av1", "clean", "videos"]


def test_parse_byte_size_and_bitrate_helpers():
    assert av1._parse_byte_size("10M") == 10 * 1024 * 1024
    assert av1._parse_byte_size("1.5GB") == int(1.5 * 1024**3)
    assert av1._parse_bitrate_to_bps("2.5m") == 2_500_000
    assert av1._parse_bitrate_to_bps("2500k") == 2_500_000


def test_output_size_caps_reduce_bitrate():
    capped, notes = av1.apply_output_size_bitrate_caps(
        4_000_000,
        input_file_bytes=100 * 1024 * 1024,
        duration_sec=100.0,
        input_stream_bps=8_000_000,
        max_output_bytes=20 * 1024 * 1024,
        min_shrink_percent=50.0,
    )
    assert capped < 4_000_000
    assert notes


def test_build_output_paths_uses_codec_suffix(tmp_path):
    source = tmp_path / "movie.mp4"
    out_dir = tmp_path / "out"
    resolved_dir, output_path, temp_output = av1._build_output_paths(str(source), str(out_dir), "av1")

    assert resolved_dir == str(out_dir)
    assert output_path.endswith("movie-AV1.mkv")
    assert temp_output.endswith("movie-AV1.mkv.temp.mkv")
    assert out_dir.exists()


def test_vaapi_command_does_not_include_svt_flags(monkeypatch):
    monkeypatch.setenv("AV1_VAAPI_DEVICE", "/dev/dri/test")
    command, pix_fmt = av1._build_ffmpeg_command(
        ffmpeg_cmd="ffmpeg",
        input_path="input.mp4",
        output_path="output.mkv",
        temp_output="output.mkv.temp.mkv",
        encoder_name="av1_vaapi",
        hw_type="vaapi",
        codec="av1",
        target_bitrate_int=2_000_000,
        effective_cpu_threads=4,
        effective_max_width=1280,
        audio_channels=2,
    )

    assert pix_fmt == "nv12"
    assert "-vaapi_device" in command
    assert "hwupload" in command[command.index("-vf") + 1]
    assert "-svtav1-params" not in command
    assert "-preset" not in command


def test_cpu_command_includes_svt_thread_setting():
    command, pix_fmt = av1._build_ffmpeg_command(
        ffmpeg_cmd="ffmpeg",
        input_path="input.mp4",
        output_path="output.mkv",
        temp_output="output.mkv.temp.mkv",
        encoder_name="libsvtav1",
        hw_type="cpu",
        codec="av1",
        target_bitrate_int=2_000_000,
        effective_cpu_threads=6,
        effective_max_width=1920,
        audio_channels=6,
    )

    assert pix_fmt == "yuv420p"
    assert "-svtav1-params" in command
    assert "lp=6" in command
    assert "channelmap=map=FL-FL|FR-FR|FC-FC|LFE-LFE|SL-BL|SR-BR" in command


def test_inspect_transcoding_need_uses_active_codec(monkeypatch):
    payload = {
        "streams": [
            {"codec_type": "video", "codec_name": "av1"},
        ]
    }

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(av1.subprocess, "run", fake_run)
    monkeypatch.setitem(av1.ACTIVE_ENCODER, "codec", "av1")

    assert av1.inspect_transcoding_need("movie.mkv") == "already-av1"
