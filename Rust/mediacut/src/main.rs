mod cli;
mod color;
mod ffmpeg;
mod plan;
mod time;

use anyhow::{bail, Context, Result};
use clap::Parser;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use crate::cli::Cli;
use crate::ffmpeg::{
    build_concat_args, build_extract_args, format_command_line, probe_duration, resolve_ffmpeg,
    resolve_ffprobe, run_ffmpeg, write_concat_list,
};
use crate::plan::{build_plan, output_paths, CutPlan, Mode};

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

    if !input.is_file() {
        bail!("input is not a file: {}", input.display());
    }

    let ffmpeg = resolve_ffmpeg(cli.ffmpeg.as_deref())?;

    let duration = if !cli.removes.is_empty() {
        let ffprobe = resolve_ffprobe(cli.ffprobe.as_deref())?;
        Some(probe_duration(&ffprobe, input)?)
    } else {
        None
    };

    let cut_plan = build_plan(&cli, duration)?;
    let outputs = output_paths(input, cli.output.as_deref(), &cut_plan)?;

    ensure_parent_dirs(&outputs, cli.dry_run)?;

    for out in &outputs {
        if out.exists() && !cli.force {
            bail!(
                "output already exists: {} (use --force to overwrite)",
                out.display()
            );
        }
    }

    if cut_plan.join && cut_plan.intervals.len() == 1 {
        // Single interval → one extract
        extract_one(
            &ffmpeg,
            input,
            &outputs[0],
            cut_plan.intervals[0],
            cli.reencode,
            cli.force,
            cli.dry_run,
        )?;
        if !cli.dry_run {
            color::success(&format!(
                "success: {} -> {}",
                input.display(),
                outputs[0].display()
            ));
        }
        return Ok(());
    }

    if !cut_plan.join {
        // Multi-file extract
        for (interval, out) in cut_plan.intervals.iter().zip(outputs.iter()) {
            extract_one(
                &ffmpeg,
                input,
                out,
                *interval,
                cli.reencode,
                cli.force,
                cli.dry_run,
            )?;
            if !cli.dry_run {
                color::success(&format!(
                    "success: {} [{}-{}] -> {}",
                    input.display(),
                    interval.start,
                    interval.end,
                    out.display()
                ));
            }
        }
        return Ok(());
    }

    // Join multiple intervals (extract --join or --remove)
    join_intervals(&cli, &ffmpeg, input, &cut_plan, &outputs[0])?;
    if !cli.dry_run {
        color::success(&format!(
            "success: {} -> {}",
            input.display(),
            outputs[0].display()
        ));
    }
    Ok(())
}

fn extract_one(
    ffmpeg: &Path,
    input: &Path,
    output: &Path,
    interval: time::Interval,
    reencode: bool,
    force: bool,
    dry_run: bool,
) -> Result<()> {
    let args = build_extract_args(input, output, interval, reencode, force);
    let cmdline = format_command_line(ffmpeg, &args);
    if dry_run {
        println!("{cmdline}");
        return Ok(());
    }
    println!(
        "{} [{}-{}] -> {}",
        input.display(),
        interval.start,
        interval.end,
        output.display()
    );
    run_ffmpeg(ffmpeg, &args)
}

fn join_intervals(
    cli: &Cli,
    ffmpeg: &Path,
    input: &Path,
    cut_plan: &CutPlan,
    final_out: &Path,
) -> Result<()> {
    let temp_dir = temp_work_dir()?;
    if !cli.dry_run {
        fs::create_dir_all(&temp_dir)
            .with_context(|| format!("failed to create temp dir {}", temp_dir.display()))?;
    }

    let ext = input
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("mkv");

    let mut parts = Vec::with_capacity(cut_plan.intervals.len());
    for (i, interval) in cut_plan.intervals.iter().enumerate() {
        let part = temp_dir.join(format!("part_{i:03}.{ext}"));
        extract_one(
            ffmpeg,
            input,
            &part,
            *interval,
            cli.reencode,
            true, // always overwrite temps
            cli.dry_run,
        )?;
        parts.push(part);
    }

    let list_file = temp_dir.join("concat.txt");
    let concat_args = build_concat_args(&list_file, final_out, cli.reencode, cli.force);
    let cmdline = format_command_line(ffmpeg, &concat_args);

    if cli.dry_run {
        println!("# would write concat list with {} parts", parts.len());
        println!("{cmdline}");
        return Ok(());
    }

    write_concat_list(&list_file, &parts)?;
    println!("concat {} parts -> {}", parts.len(), final_out.display());
    let result = run_ffmpeg(ffmpeg, &concat_args);

    // Best-effort cleanup
    let _ = fs::remove_dir_all(&temp_dir);

    result.with_context(|| {
        format!(
            "concat failed for {} ({})",
            final_out.display(),
            match cut_plan.mode {
                Mode::Remove => "remove mode",
                Mode::Extract => "join mode",
            }
        )
    })
}

fn ensure_parent_dirs(outputs: &[PathBuf], dry_run: bool) -> Result<()> {
    if dry_run {
        return Ok(());
    }
    for out in outputs {
        if let Some(parent) = out.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)
                    .with_context(|| format!("failed to create {}", parent.display()))?;
            }
        }
    }
    Ok(())
}

fn temp_work_dir() -> Result<PathBuf> {
    let base = env::temp_dir().join(format!(
        "mediacut-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis())
            .unwrap_or(0)
    ));
    Ok(base)
}
