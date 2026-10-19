use clap::{Parser, ValueEnum};
use std::path::PathBuf;

/// Extract audio from one or more video files using ffmpeg.
#[derive(Debug, Parser)]
#[command(
    name = "vid2audio",
    about = "Convert video files to audio (default: Opus)",
    disable_help_subcommand = true
)]
pub struct Cli {
    /// Video file(s) to convert
    #[arg(required = true, value_name = "INPUT")]
    pub inputs: Vec<PathBuf>,

    /// Output audio format
    #[arg(long, value_enum, default_value_t = AudioFormat::Opus)]
    pub format: AudioFormat,

    /// Directory for output files (default: same directory as each input)
    #[arg(short = 'o', long = "output-dir", value_name = "DIR")]
    pub output_dir: Option<PathBuf>,

    /// Audio bitrate in kbps (ignored for flac; defaults: opus 128, mp3/aac 192)
    #[arg(long, value_name = "KBPS")]
    pub bitrate: Option<u32>,

    /// Path to ffmpeg binary (overrides FFMPEG_PATH env and PATH)
    #[arg(long, value_name = "PATH")]
    pub ffmpeg: Option<PathBuf>,

    /// Overwrite existing output files
    #[arg(long)]
    pub force: bool,

    /// Print ffmpeg commands without running them
    #[arg(long)]
    pub dry_run: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum AudioFormat {
    Opus,
    Mp3,
    Aac,
    Flac,
}
