use anyhow::{bail, Context, Result};
use clap::Parser;
use mediacut::color;
use mediacut::ffmpeg::{
    format_command_line, probe_duration, resolve_ffmpeg, resolve_ffprobe, run_ffmpeg,
};
use mediacut::time::{parse_time, Time};
use mediacut::wave::{
    bucket_peaks, build_pcm_args, build_png_args, decode_pcm_f32le, print_terminal, TimeWindow,
};
use std::fs;
use std::io::{self, Write};
use std::path::PathBuf;
use std::process::ExitCode;

/// Show a terminal and/or PNG waveform for audio/video via ffmpeg.
#[derive(Debug, Parser)]
#[command(
    name = "mediawave",
    about = "Show waveform of audio/video (terminal and/or PNG)",
    disable_help_subcommand = true
)]
struct Cli {
    /// Input media file (audio or video with audio)
    #[arg(value_name = "INPUT")]
    input: PathBuf,

    /// Write waveform PNG (implies image mode; add --terminal for both)
    #[arg(short = 'o', long = "output", value_name = "PATH")]
    output: Option<PathBuf>,

    /// Also print terminal waveform when writing a PNG
    #[arg(long)]
    terminal: bool,

    /// Waveform width in columns (terminal) or pixels (PNG)
    #[arg(long, value_name = "N")]
    width: Option<u32>,

    /// Waveform height in rows (terminal) or pixels (PNG)
    #[arg(long, value_name = "N")]
    height: Option<u32>,

    /// Window start time
    #[arg(long, value_name = "TIME")]
    start: Option<String>,

    /// Window end time (with --start)
    #[arg(long, value_name = "TIME")]
    end: Option<String>,

    /// Window duration from --start
    #[arg(long, value_name = "TIME")]
    duration: Option<String>,

    /// Hide the time axis under the waveform
    #[arg(long = "no-timeline")]
    no_timeline: bool,

    /// Path to ffmpeg binary (overrides FFMPEG_PATH env and PATH)
    #[arg(long, value_name = "PATH")]
    ffmpeg: Option<PathBuf>,

    /// Path to ffprobe binary (overrides FFPROBE_PATH env and PATH)
    #[arg(long, value_name = "PATH")]
    ffprobe: Option<PathBuf>,

    /// Overwrite existing PNG
    #[arg(long)]
    force: bool,

    /// Print ffmpeg commands without running them
    #[arg(long)]
    dry_run: bool,
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            color::error(&format!("error: {err:#}"));
            ExitCode::from(1)
        }
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    let input = &cli.input;

    if !cli.dry_run && !input.is_file() {
        bail!("input is not a file: {}", input.display());
    }

    let want_png = cli.output.is_some();
    let want_term = !want_png || cli.terminal;
    if !want_png && !want_term {
        bail!("nothing to do");
    }

    let window = TimeWindow {
        start: optional_time(cli.start.as_deref())?,
        end: optional_time(cli.end.as_deref())?,
        duration: optional_time(cli.duration.as_deref())?,
    }
    .validate()?;

    let ffmpeg = resolve_ffmpeg(cli.ffmpeg.as_deref())?;

    let timeline = if cli.no_timeline {
        None
    } else if window.span_known() {
        Some(window.absolute_range(None)?)
    } else if cli.dry_run {
        // Placeholder range so --dry-run still shows timeline filters
        Some((0.0, 60.0))
    } else {
        let ffprobe = resolve_ffprobe(cli.ffprobe.as_deref())?;
        let media_dur = probe_duration(&ffprobe, input)?;
        Some(window.absolute_range(Some(media_dur))?)
    };

    let term_w = cli.width.unwrap_or(80) as usize;
    let term_h = cli.height.unwrap_or(12) as usize;
    let png_w = cli.width.unwrap_or(1280);
    let png_h = cli.height.unwrap_or(240);

    if want_term {
        let pcm_args = build_pcm_args(input, window);
        if cli.dry_run {
            println!("{}", format_command_line(&ffmpeg, &pcm_args));
        } else {
            let samples = decode_pcm_f32le(&ffmpeg, input, window)?;
            let peaks = bucket_peaks(&samples, term_w);
            let mut stdout = io::stdout().lock();
            print_terminal(&peaks, term_h, timeline, &mut stdout)?;
            stdout.flush().ok();
        }
    }

    if let Some(out) = &cli.output {
        if out.exists() && !cli.force && !cli.dry_run {
            bail!(
                "output already exists: {} (use --force to overwrite)",
                out.display()
            );
        }
        if let Some(parent) = out.parent() {
            if !parent.as_os_str().is_empty() && !cli.dry_run {
                fs::create_dir_all(parent)
                    .with_context(|| format!("failed to create {}", parent.display()))?;
            }
        }

        let args = build_png_args(input, out, png_w, png_h, window, cli.force, timeline);
        if cli.dry_run {
            println!("{}", format_command_line(&ffmpeg, &args));
        } else {
            run_ffmpeg(&ffmpeg, &args)?;
            color::success(&format!(
                "success: {} -> {}",
                input.display(),
                out.display()
            ));
        }
    }

    Ok(())
}

fn optional_time(s: Option<&str>) -> Result<Option<Time>> {
    match s {
        Some(v) => Ok(Some(parse_time(v)?)),
        None => Ok(None),
    }
}
