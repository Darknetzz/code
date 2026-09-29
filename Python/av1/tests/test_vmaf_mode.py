"""Tests for VMAF/CRF mode (ab-av1 crf-search) and full stream mapping."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import av1  # noqa: E402

DONE = (
    '{"crf":29.75,"from_cache":false,"predicted_encode_percent":13.78,'
    '"predicted_encode_seconds":13.0,"predicted_encode_size":68549279,'
    '"type":"crf-search-done","vmaf":95.16}'
)
ATTEMPT = (
    '{"crf":37.5,"from_cache":true,"predicted_encode_percent":18.9,'
    '"predicted_encode_seconds":17.0,"predicted_encode_size":11097844,'
    '"type":"sample-encode-done","vmaf":89.39}'
)
ERROR = '{"message":"Failed to find a suitable crf","type":"crf-search-error"}'


def test_parse_crf_search_done():
    result = av1.parse_crf_search_output([ATTEMPT + "\n", DONE + "\n"])
    assert result.ok
    assert result.crf == 29.75
    assert round(result.vmaf, 2) == 95.16
    assert result.predicted_percent == 13.78
    assert result.last_attempt["crf"] == 37.5


def test_parse_crf_search_no_suitable_crf():
    result = av1.parse_crf_search_output([ATTEMPT, ERROR])
    assert not result.ok
    assert result.no_suitable_crf
    assert result.last_attempt["vmaf"] == 89.39


def test_parse_crf_search_garbage_is_error():
    result = av1.parse_crf_search_output(["Error: something broke", "", "{not json"])
    assert not result.ok
    assert not result.no_suitable_crf


def test_format_crf():
    assert av1._format_crf(31.0) == "31"
    assert av1._format_crf(29.75) == "29.75"


def test_crf_search_command_mirrors_encode_settings():
    cmd = av1._build_crf_search_command(
        "in.mkv", min_vmaf=95, preset=6, max_encoded_percent=80, cpu_threads=4, vfilter=None
    )
    assert cmd[1] == "crf-search"
    for flag, value in (
        ("--preset", "6"),
        ("--pix-format", av1.VMAF_PIX_FMT),
        ("--min-vmaf", "95"),
        ("--max-encoded-percent", "80"),
        ("--stdout-format", "json"),
        ("--svt", "lp=4"),
    ):
        assert cmd[cmd.index(flag) + 1] == value
    assert "--vfilter" not in cmd


def test_crf_search_vfilter_only_when_downscaling():
    assert av1._crf_search_vfilter({"display_width": 1280, "width": 1280}, 1920) is None
    vf = av1._crf_search_vfilter({"display_width": 3840, "width": 3840}, 1920)
    assert vf and "scale='min(1920,iw)'" in vf and "transpose" not in vf


def test_cpu_crf_command_uses_crf_not_bitrate():
    command, pix_fmt = av1._build_ffmpeg_command(
        ffmpeg_cmd="ffmpeg",
        input_path="in.mkv",
        output_path="out.mkv",
        temp_output="out.mkv.temp.mkv",
        encoder_name="libsvtav1",
        hw_type="cpu",
        codec="av1",
        target_bitrate_int=0,
        effective_cpu_threads=4,
        effective_max_width=1920,
        audio_channels=2,
        crf=31.0,
        fps=25.0,
        streams=[],
    )
    assert pix_fmt == "yuv420p10le"
    assert "-b:v" not in command
    params = command[command.index("-svtav1-params") + 1]
    assert "crf=31" in params and "lp=4" in params and "scd=1" in params
    assert command[command.index("-g") + 1] == "250"
    assert command[command.index("-preset") + 1] == str(av1.SVT_PRESET)
    assert command[-1] == "out.mkv.temp.mkv"


def _streams():
    return [
        {"index": 0, "codec_type": "video", "codec_name": "h264", "channels": None, "channel_layout": "", "attached_pic": False},
        {"index": 1, "codec_type": "audio", "codec_name": "ac3", "channels": 6, "channel_layout": "5.1(side)", "attached_pic": False},
        {"index": 2, "codec_type": "audio", "codec_name": "opus", "channels": 2, "channel_layout": "stereo", "attached_pic": False},
        {"index": 3, "codec_type": "subtitle", "codec_name": "subrip", "channels": None, "channel_layout": "", "attached_pic": False},
        {"index": 4, "codec_type": "subtitle", "codec_name": "mov_text", "channels": None, "channel_layout": "", "attached_pic": False},
        {"index": 5, "codec_type": "subtitle", "codec_name": "eia_608", "channels": None, "channel_layout": "", "attached_pic": False},
        {"index": 6, "codec_type": "attachment", "codec_name": "ttf", "channels": None, "channel_layout": "", "attached_pic": False},
        {"index": 7, "codec_type": "video", "codec_name": "mjpeg", "channels": None, "channel_layout": "", "attached_pic": True},
        {"index": 8, "codec_type": "data", "codec_name": "bin_data", "channels": None, "channel_layout": "", "attached_pic": False},
    ]


def test_stream_map_keeps_all_audio_and_subs():
    args, notes = av1._build_stream_map_args(_streams(), input_is_mkv=True)
    maps = [args[i + 1] for i, a in enumerate(args) if a == "-map"]
    assert maps == ["0:0", "0:1", "0:2", "0:3", "0:4", "0:6"]
    # 5.1(side) AC3 -> Opus with channelmap; existing Opus copied
    assert args[args.index("-c:a:0") + 1] == "libopus"
    assert "channelmap" in args[args.index("-filter:a:0") + 1]
    assert args[args.index("-c:a:1") + 1] == "copy"
    # subrip copied, mov_text converted, eia_608 dropped
    assert args[args.index("-c:s:0") + 1] == "copy"
    assert args[args.index("-c:s:1") + 1] == "srt"
    assert "-c:s:2" not in args
    assert args[args.index("-c:t") + 1] == "copy"
    assert "-map_metadata" in args and "-map_chapters" in args
    joined = " ".join(notes)
    assert "cover art" in joined and "eia_608" in joined and "data stream" in joined


def test_stream_map_skips_attachments_for_non_mkv():
    args, _ = av1._build_stream_map_args(_streams(), input_is_mkv=False)
    assert "0:6" not in args
    assert "-c:t" not in args


def test_plain_51_layout_gets_no_channelmap():
    streams = [
        {"index": 0, "codec_type": "video", "codec_name": "h264", "channels": None, "channel_layout": "", "attached_pic": False},
        {"index": 1, "codec_type": "audio", "codec_name": "eac3", "channels": 6, "channel_layout": "5.1", "attached_pic": False},
    ]
    args, _ = av1._build_stream_map_args(streams, input_is_mkv=True)
    assert "-filter:a:0" not in args


def test_opus_bitrate_scales_with_channels(monkeypatch):
    monkeypatch.setattr(av1, "AUDIO_BITRATE", "64k")
    assert av1._opus_bitrate_for_channels(None) == "64k"
    assert av1._opus_bitrate_for_channels(1) == "64k"
    assert av1._opus_bitrate_for_channels(2) == "64k"
    assert av1._opus_bitrate_for_channels(6) == "192k"
    assert av1._opus_bitrate_for_channels(8) == "256k"
    monkeypatch.setattr(av1, "AUDIO_BITRATE", "96k")
    assert av1._opus_bitrate_for_channels(6) == "288k"


def test_stream_map_uses_channel_scaled_bitrate(monkeypatch):
    monkeypatch.setattr(av1, "AUDIO_BITRATE", "64k")
    args, _ = av1._build_stream_map_args(_streams(), input_is_mkv=True)
    assert args[args.index("-b:a:0") + 1] == "192k"
