use clap::Parser;
use std::path::PathBuf;

/// Cut video/audio files with ffmpeg (extract or remove time ranges).
#[derive(Debug, Parser)]
#[command(
    name = "mediacut",
    about = "Cut video/audio files (extract segments or remove ranges)",
    disable_help_subcommand = true
)]
pub struct Cli {
    /// Input media file
    #[arg(value_name = "INPUT")]
    pub input: PathBuf,

    /// Extract range START-END (repeatable). Time: SS, MM:SS, or HH:MM:SS
    #[arg(short = 's', long = "segment", value_name = "START-END")]
    pub segments: Vec<String>,

    /// Extract start time (use with --end or --duration)
    #[arg(long, value_name = "TIME")]
    pub start: Option<String>,

    /// Extract end time (with --start)
    #[arg(long, value_name = "TIME")]
    pub end: Option<String>,

    /// Extract duration from --start
    #[arg(long, value_name = "TIME")]
    pub duration: Option<String>,

    /// Remove range START-END from the file (repeatable); remaining parts are joined
    #[arg(long = "remove", value_name = "START-END")]
    pub removes: Vec<String>,

    /// Join extracted segments into one output file
    #[arg(long)]
    pub join: bool,

    /// Output file (single/join/remove) or directory (multi-segment without --join)
    #[arg(short = 'o', long = "output", value_name = "PATH")]
    pub output: Option<PathBuf>,

    /// Re-encode for frame-accurate cuts (slower; default is stream copy)
    #[arg(long)]
    pub reencode: bool,

    /// Path to ffmpeg binary (overrides FFMPEG_PATH env and PATH)
    #[arg(long, value_name = "PATH")]
    pub ffmpeg: Option<PathBuf>,

    /// Path to ffprobe binary (overrides FFPROBE_PATH env and PATH)
    #[arg(long, value_name = "PATH")]
    pub ffprobe: Option<PathBuf>,

    /// Overwrite existing output files
    #[arg(long)]
    pub force: bool,

    /// Print ffmpeg commands without running them
    #[arg(long)]
    pub dry_run: bool,
}
