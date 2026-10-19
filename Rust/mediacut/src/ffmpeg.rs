use crate::time::Interval;
use anyhow::{bail, Context, Result};
use std::env;
use std::ffi::OsString;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Resolve ffmpeg: CLI flag, then `FFMPEG_PATH`, then `ffmpeg` on PATH.
pub fn resolve_ffmpeg(cli_path: Option<&Path>) -> Result<PathBuf> {
    resolve_tool(cli_path, "FFMPEG_PATH", "ffmpeg")
}

/// Resolve ffprobe: CLI flag, then `FFPROBE_PATH`, then `ffprobe` on PATH.
pub fn resolve_ffprobe(cli_path: Option<&Path>) -> Result<PathBuf> {
    resolve_tool(cli_path, "FFPROBE_PATH", "ffprobe")
}

fn resolve_tool(cli_path: Option<&Path>, env_key: &str, bare_name: &str) -> Result<PathBuf> {
    if let Some(path) = cli_path {
        if path.is_file() {
            return Ok(path.to_path_buf());
        }
        bail!("{bare_name} not found at {}", path.display());
    }

    if let Ok(env_path) = env::var(env_key) {
        let path = PathBuf::from(&env_path);
        if path.is_file() {
            return Ok(path);
        }
        if !env_path.contains(['/', '\\']) {
            return Ok(PathBuf::from(env_path));
        }
        bail!("{env_key} is set but not a file: {env_path}");
    }

    which_bin(bare_name).with_context(|| {
        format!(
            "{bare_name} not found on PATH; install ffmpeg or pass --{bare_name} / set {env_key}"
        )
    })
}

fn which_bin(bare_name: &str) -> Option<PathBuf> {
    let exe = if cfg!(windows) {
        format!("{bare_name}.exe")
    } else {
        bare_name.to_string()
    };
    let path_var = env::var_os("PATH")?;
    for dir in env::split_paths(&path_var) {
        let candidate = dir.join(&exe);
        if candidate.is_file() {
            return Some(candidate);
        }
        if cfg!(windows) {
            let bare = dir.join(bare_name);
            if bare.is_file() {
                return Some(bare);
            }
        }
    }
    None
}

/// Probe media duration in seconds via ffprobe.
pub fn probe_duration(ffprobe: &Path, input: &Path) -> Result<f64> {
    let output = Command::new(ffprobe)
        .args([
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
        ])
        .arg(input)
        .output()
        .with_context(|| format!("failed to start ffprobe at {}", ffprobe.display()))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        bail!("ffprobe failed: {stderr}");
    }
    let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let duration: f64 = text
        .parse()
        .with_context(|| format!("ffprobe returned non-numeric duration: `{text}`"))?;
    if !(duration.is_finite() && duration > 0.0) {
        bail!("invalid media duration from ffprobe: {duration}");
    }
    Ok(duration)
}

/// Build argv to extract one interval to `output`.
pub fn build_extract_args(
    input: &Path,
    output: &Path,
    interval: Interval,
    reencode: bool,
    force: bool,
) -> Vec<OsString> {
    let mut args: Vec<OsString> = vec![
        OsString::from("-hide_banner"),
        OsString::from("-loglevel"),
        OsString::from("error"),
        OsString::from(if force { "-y" } else { "-n" }),
    ];

    let start = interval.start.to_ffmpeg();
    let end = interval.end.to_ffmpeg();
    let duration = format!("{:.3}", interval.duration());

    if reencode {
        // Accurate seek: decode first, then -ss / -to
        args.push(OsString::from("-i"));
        args.push(input.as_os_str().to_os_string());
        args.push(OsString::from("-ss"));
        args.push(OsString::from(start));
        args.push(OsString::from("-to"));
        args.push(OsString::from(end));
        // Let ffmpeg pick encoders from the output container.
    } else {
        // Fast path: keyframe-aligned stream copy
        args.push(OsString::from("-ss"));
        args.push(OsString::from(start));
        args.push(OsString::from("-i"));
        args.push(input.as_os_str().to_os_string());
        args.push(OsString::from("-t"));
        args.push(OsString::from(duration));
        args.push(OsString::from("-c"));
        args.push(OsString::from("copy"));
        args.push(OsString::from("-avoid_negative_ts"));
        args.push(OsString::from("make_zero"));
    }

    args.push(output.as_os_str().to_os_string());
    args
}

/// Build argv for concat demuxer (list file → output).
pub fn build_concat_args(
    list_file: &Path,
    output: &Path,
    reencode: bool,
    force: bool,
) -> Vec<OsString> {
    let mut args: Vec<OsString> = vec![
        OsString::from("-hide_banner"),
        OsString::from("-loglevel"),
        OsString::from("error"),
        OsString::from(if force { "-y" } else { "-n" }),
        OsString::from("-f"),
        OsString::from("concat"),
        OsString::from("-safe"),
        OsString::from("0"),
        OsString::from("-i"),
        list_file.as_os_str().to_os_string(),
    ];
    if reencode {
        // Auto encoders from container
    } else {
        args.push(OsString::from("-c"));
        args.push(OsString::from("copy"));
    }
    args.push(output.as_os_str().to_os_string());
    args
}

/// Write an ffmpeg concat demuxer list file.
pub fn write_concat_list(list_file: &Path, parts: &[PathBuf]) -> Result<()> {
    let mut body = String::new();
    for part in parts {
        let path = part
            .canonicalize()
            .with_context(|| format!("cannot canonicalize {}", part.display()))?;
        // concat demuxer: file 'path' with single quotes escaped as '\''
        let s = path.to_string_lossy().replace('\'', "'\\''");
        body.push_str(&format!("file '{s}'\n"));
    }
    if let Some(parent) = list_file.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create {}", parent.display()))?;
    }
    fs::write(list_file, body)
        .with_context(|| format!("failed to write concat list {}", list_file.display()))?;
    Ok(())
}

pub fn format_command_line(bin: &Path, args: &[OsString]) -> String {
    let mut parts = Vec::with_capacity(args.len() + 1);
    parts.push(shell_quote(&bin.display().to_string()));
    for arg in args {
        parts.push(shell_quote(&arg.to_string_lossy()));
    }
    parts.join(" ")
}

fn shell_quote(s: &str) -> String {
    if s.is_empty() {
        return "\"\"".to_string();
    }
    if s.chars()
        .any(|c| c.is_whitespace() || matches!(c, '"' | '\'' | '\\'))
    {
        format!("\"{}\"", s.replace('"', "\\\""))
    } else {
        s.to_string()
    }
}

pub fn run_ffmpeg(ffmpeg: &Path, args: &[OsString]) -> Result<()> {
    let status = Command::new(ffmpeg)
        .args(args)
        .status()
        .with_context(|| format!("failed to start ffmpeg at {}", ffmpeg.display()))?;

    if !status.success() {
        let code = status
            .code()
            .map(|c| c.to_string())
            .unwrap_or_else(|| "signal".to_string());
        bail!("ffmpeg exited with status {code}");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::time::{Interval, Time};

    #[test]
    fn extract_copy_places_ss_before_input() {
        let interval = Interval::new(Time(1.0), Time(2.0)).unwrap();
        let args = build_extract_args(
            Path::new("in.mp4"),
            Path::new("out.mp4"),
            interval,
            false,
            true,
        );
        let joined: Vec<String> = args
            .iter()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        let ss = joined.iter().position(|a| a == "-ss").unwrap();
        let i = joined.iter().position(|a| a == "-i").unwrap();
        assert!(ss < i);
        assert!(joined.contains(&"-c".to_string()));
        assert!(joined.contains(&"copy".to_string()));
        assert!(joined.contains(&"-y".to_string()));
    }

    #[test]
    fn extract_reencode_places_ss_after_input() {
        let interval = Interval::new(Time(1.0), Time(2.0)).unwrap();
        let args = build_extract_args(
            Path::new("in.mp4"),
            Path::new("out.mp4"),
            interval,
            true,
            false,
        );
        let joined: Vec<String> = args
            .iter()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        let ss = joined.iter().position(|a| a == "-ss").unwrap();
        let i = joined.iter().position(|a| a == "-i").unwrap();
        assert!(i < ss);
        assert!(!joined.iter().any(|a| a == "copy"));
        assert!(joined.contains(&"-n".to_string()));
    }

    #[test]
    fn concat_copy_has_demuxer() {
        let args = build_concat_args(Path::new("list.txt"), Path::new("out.mp4"), false, true);
        let joined: Vec<String> = args
            .iter()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        assert!(joined.contains(&"concat".to_string()));
        assert!(joined.contains(&"copy".to_string()));
    }
}
