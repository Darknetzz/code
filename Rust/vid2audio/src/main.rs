mod cli;
mod ffmpeg;

use anyhow::{bail, Context, Result};
use clap::Parser;
use std::fs;
use std::process::ExitCode;

use crate::cli::Cli;
use crate::ffmpeg::{
    build_args, format_command_line, format_spec, output_path, resolve_ffmpeg, run_ffmpeg,
};

fn main() -> ExitCode {
    match run() {
        Ok(0) => ExitCode::SUCCESS,
        Ok(_) => ExitCode::from(1),
        Err(err) => {
            eprintln!("error: {err:#}");
            ExitCode::from(1)
        }
    }
}

fn run() -> Result<i32> {
    let cli = Cli::parse();
    let spec = format_spec(cli.format);
    let ffmpeg = resolve_ffmpeg(cli.ffmpeg.as_deref())?;

    if let Some(dir) = &cli.output_dir {
        if !cli.dry_run {
            fs::create_dir_all(dir)
                .with_context(|| format!("failed to create output directory {}", dir.display()))?;
        }
    }

    let mut failures = 0usize;

    for input in &cli.inputs {
        if let Err(err) = convert_one(&cli, &ffmpeg, &spec, input) {
            eprintln!("error: {}: {err:#}", input.display());
            failures += 1;
        }
    }

    Ok(if failures == 0 { 0 } else { 1 })
}

fn convert_one(
    cli: &Cli,
    ffmpeg: &std::path::Path,
    spec: &ffmpeg::FormatSpec,
    input: &std::path::Path,
) -> Result<()> {
    if !input.is_file() {
        bail!("input is not a file");
    }

    let output = output_path(input, cli.output_dir.as_deref(), spec.extension)?;

    if output.exists() && !cli.force {
        bail!(
            "output already exists: {} (use --force to overwrite)",
            output.display()
        );
    }

    let args = build_args(input, &output, spec, cli.bitrate, cli.force);
    let cmdline = format_command_line(ffmpeg, &args);

    if cli.dry_run {
        println!("{cmdline}");
        return Ok(());
    }

    println!("{} -> {}", input.display(), output.display());
    run_ffmpeg(ffmpeg, &args)?;
    Ok(())
}
