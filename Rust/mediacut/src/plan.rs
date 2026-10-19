use crate::cli::Cli;
use crate::time::{
    keep_from_removes, parse_time, validate_non_overlapping, Interval, Time,
};
use anyhow::{bail, Context, Result};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Extract,
    Remove,
}

#[derive(Debug, Clone)]
pub struct CutPlan {
    pub mode: Mode,
    /// Intervals to keep / extract (in order).
    pub intervals: Vec<Interval>,
    /// When true, write one joined output; otherwise one file per interval.
    pub join: bool,
}

pub fn build_plan(cli: &Cli, duration: Option<f64>) -> Result<CutPlan> {
    let has_segments = !cli.segments.is_empty();
    let has_start = cli.start.is_some();
    let has_removes = !cli.removes.is_empty();

    if has_removes && (has_segments || has_start) {
        bail!("cannot combine --remove with --segment / --start");
    }
    if !has_removes && !has_segments && !has_start {
        bail!("specify --segment, --start/--end, or --remove");
    }
    if cli.join && has_removes {
        bail!("--join is only valid with extract mode (--segment / --start)");
    }
    if cli.end.is_some() && cli.duration.is_some() {
        bail!("use either --end or --duration, not both");
    }
    if (cli.end.is_some() || cli.duration.is_some()) && cli.start.is_none() {
        bail!("--end / --duration require --start");
    }
    if has_start && !cli.segments.is_empty() {
        bail!("use either --segment or --start, not both");
    }

    if has_removes {
        let duration = duration.context("duration required for --remove (ffprobe)")?;
        let mut removes = Vec::with_capacity(cli.removes.len());
        for spec in &cli.removes {
            removes.push(Interval::parse_range(spec)?);
        }
        let intervals = keep_from_removes(&removes, duration)?;
        return Ok(CutPlan {
            mode: Mode::Remove,
            intervals,
            join: true,
        });
    }

    let mut intervals = Vec::new();
    if has_start {
        intervals.push(interval_from_start_end(cli)?);
    }
    for spec in &cli.segments {
        intervals.push(Interval::parse_range(spec)?);
    }
    validate_non_overlapping(&intervals)?;

    // Single segment → one file; multi defaults to separate files unless --join.
    let join = intervals.len() == 1 || cli.join;

    Ok(CutPlan {
        mode: Mode::Extract,
        intervals,
        join,
    })
}

fn interval_from_start_end(cli: &Cli) -> Result<Interval> {
    let start = parse_time(cli.start.as_deref().unwrap())?;
    if let Some(end_s) = &cli.end {
        let end = parse_time(end_s)?;
        return Interval::new(start, end);
    }
    if let Some(dur_s) = &cli.duration {
        let dur = parse_time(dur_s)?;
        if dur.as_secs() <= 0.0 {
            bail!("--duration must be positive");
        }
        return Interval::new(start, Time(start.as_secs() + dur.as_secs()));
    }
    bail!("--start requires --end or --duration");
}

/// Resolve output path(s) for a plan.
pub fn output_paths(
    input: &Path,
    output: Option<&Path>,
    plan: &CutPlan,
) -> Result<Vec<PathBuf>> {
    let ext = input
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("mkv");
    let stem = input
        .file_stem()
        .and_then(|s| s.to_str())
        .context("input has no file name")?;

    if plan.join {
        let path = match output {
            Some(p) if is_dir_hint(p) => p.join(format!("{stem}_cut.{ext}")),
            Some(p) => p.to_path_buf(),
            None => default_beside(input, &format!("{stem}_cut.{ext}"))?,
        };
        return Ok(vec![path]);
    }

    // Multi-file extract
    if let Some(p) = output {
        if p.extension().is_some() && plan.intervals.len() > 1 {
            bail!("-o must be a directory when writing multiple segment files (or use --join)");
        }
        let dir = if p.exists() && p.is_dir() || p.extension().is_none() {
            p.to_path_buf()
        } else {
            bail!("-o must be a directory when writing multiple segment files");
        };
        let mut paths = Vec::with_capacity(plan.intervals.len());
        for (i, interval) in plan.intervals.iter().enumerate() {
            let name = format!(
                "{stem}_{:03}_{}-{}.{ext}",
                i + 1,
                slug_time(interval.start),
                slug_time(interval.end),
            );
            paths.push(dir.join(name));
        }
        return Ok(paths);
    }

    let mut paths = Vec::with_capacity(plan.intervals.len());
    for (i, interval) in plan.intervals.iter().enumerate() {
        let name = format!(
            "{stem}_{:03}_{}-{}.{ext}",
            i + 1,
            slug_time(interval.start),
            slug_time(interval.end),
        );
        paths.push(default_beside(input, &name)?);
    }
    Ok(paths)
}

fn slug_time(t: Time) -> String {
    t.to_ffmpeg().replace(':', "-").replace('.', "_")
}

fn default_beside(input: &Path, file_name: &str) -> Result<PathBuf> {
    let dir = input
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    Ok(dir.join(file_name))
}

fn is_dir_hint(p: &Path) -> bool {
    p.is_dir() || (p.extension().is_none() && !p.exists())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn cli_extract(segments: &[&str], join: bool) -> Cli {
        Cli {
            input: PathBuf::from("clip.mp4"),
            segments: segments.iter().map(|s| s.to_string()).collect(),
            start: None,
            end: None,
            duration: None,
            removes: vec![],
            join,
            output: None,
            reencode: false,
            ffmpeg: None,
            ffprobe: None,
            force: false,
            dry_run: false,
        }
    }

    #[test]
    fn extract_multi_no_join() {
        let cli = cli_extract(&["0-10", "20-30"], false);
        let plan = build_plan(&cli, None).unwrap();
        assert_eq!(plan.mode, Mode::Extract);
        assert!(!plan.join);
        assert_eq!(plan.intervals.len(), 2);
    }

    #[test]
    fn extract_multi_join() {
        let cli = cli_extract(&["0-10", "20-30"], true);
        let plan = build_plan(&cli, None).unwrap();
        assert!(plan.join);
    }

    #[test]
    fn start_end_sugar() {
        let mut cli = cli_extract(&[], false);
        cli.start = Some("1:00".into());
        cli.end = Some("2:00".into());
        let plan = build_plan(&cli, None).unwrap();
        assert!(plan.join);
        assert_eq!(plan.intervals[0].start.0, 60.0);
        assert_eq!(plan.intervals[0].end.0, 120.0);
    }

    #[test]
    fn remove_mode() {
        let mut cli = cli_extract(&[], false);
        cli.removes = vec!["10-20".into()];
        let plan = build_plan(&cli, Some(30.0)).unwrap();
        assert_eq!(plan.mode, Mode::Remove);
        assert!(plan.join);
        assert_eq!(plan.intervals.len(), 2);
    }

    #[test]
    fn reject_mix() {
        let mut cli = cli_extract(&["0-5"], false);
        cli.removes = vec!["10-20".into()];
        assert!(build_plan(&cli, Some(30.0)).is_err());
    }
}
