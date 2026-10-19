use crate::cli::AudioFormat;
use anyhow::{bail, Context, Result};
use std::env;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Codec, extension, and default bitrate (kbps) for a format. `None` bitrate = lossless (flac).
#[derive(Debug, Clone, Copy)]
pub struct FormatSpec {
    pub codec: &'static str,
    pub extension: &'static str,
    pub default_bitrate_kbps: Option<u32>,
}

pub fn format_spec(format: AudioFormat) -> FormatSpec {
    match format {
        AudioFormat::Opus => FormatSpec {
            codec: "libopus",
            extension: "opus",
            default_bitrate_kbps: Some(128),
        },
        AudioFormat::Mp3 => FormatSpec {
            codec: "libmp3lame",
            extension: "mp3",
            default_bitrate_kbps: Some(192),
        },
        AudioFormat::Aac => FormatSpec {
            codec: "aac",
            extension: "m4a",
            default_bitrate_kbps: Some(192),
        },
        AudioFormat::Flac => FormatSpec {
            codec: "flac",
            extension: "flac",
            default_bitrate_kbps: None,
        },
    }
}

/// Resolve ffmpeg: CLI flag, then `FFMPEG_PATH`, then `ffmpeg` on PATH.
pub fn resolve_ffmpeg(cli_path: Option<&Path>) -> Result<PathBuf> {
    if let Some(path) = cli_path {
        if path.is_file() {
            return Ok(path.to_path_buf());
        }
        bail!("ffmpeg not found at {}", path.display());
    }

    if let Ok(env_path) = env::var("FFMPEG_PATH") {
        let path = PathBuf::from(&env_path);
        if path.is_file() {
            return Ok(path);
        }
        // Allow bare command name in env (looked up via PATH by Command)
        if !env_path.contains(['/', '\\']) {
            return Ok(PathBuf::from(env_path));
        }
        bail!("FFMPEG_PATH is set but not a file: {env_path}");
    }

    which_ffmpeg().context(
        "ffmpeg not found on PATH; install ffmpeg or pass --ffmpeg / set FFMPEG_PATH",
    )
}

fn which_ffmpeg() -> Option<PathBuf> {
    let name = if cfg!(windows) { "ffmpeg.exe" } else { "ffmpeg" };
    let path_var = env::var_os("PATH")?;
    for dir in env::split_paths(&path_var) {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
        // Windows: also accept `ffmpeg` without .exe if present
        if cfg!(windows) {
            let bare = dir.join("ffmpeg");
            if bare.is_file() {
                return Some(bare);
            }
        }
    }
    None
}

pub fn output_path(input: &Path, output_dir: Option<&Path>, extension: &str) -> Result<PathBuf> {
    let stem = input
        .file_stem()
        .with_context(|| format!("input has no file name: {}", input.display()))?;
    let mut file_name = OsString::from(stem);
    file_name.push(".");
    file_name.push(extension);

    let dir = match output_dir {
        Some(dir) => dir.to_path_buf(),
        None => input
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .map(Path::to_path_buf)
            .unwrap_or_else(|| PathBuf::from(".")),
    };

    Ok(dir.join(file_name))
}

/// Build the ffmpeg argv (excluding the binary itself).
pub fn build_args(
    input: &Path,
    output: &Path,
    spec: &FormatSpec,
    bitrate_kbps: Option<u32>,
    force: bool,
) -> Vec<OsString> {
    let mut args: Vec<OsString> = vec![
        OsString::from("-hide_banner"),
        OsString::from(if force { "-y" } else { "-n" }),
        OsString::from("-i"),
        input.as_os_str().to_os_string(),
        OsString::from("-vn"),
        OsString::from("-c:a"),
        OsString::from(spec.codec),
    ];

    let bitrate = bitrate_kbps.or(spec.default_bitrate_kbps);
    if let Some(kbps) = bitrate {
        args.push(OsString::from("-b:a"));
        args.push(OsString::from(format!("{kbps}k")));
    }

    args.push(output.as_os_str().to_os_string());
    args
}

pub fn format_command_line(ffmpeg: &Path, args: &[OsString]) -> String {
    let mut parts = Vec::with_capacity(args.len() + 1);
    parts.push(shell_quote(&ffmpeg.display().to_string()));
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

    #[test]
    fn opus_spec() {
        let s = format_spec(AudioFormat::Opus);
        assert_eq!(s.codec, "libopus");
        assert_eq!(s.extension, "opus");
        assert_eq!(s.default_bitrate_kbps, Some(128));
    }

    #[test]
    fn flac_omits_bitrate_in_args() {
        let spec = format_spec(AudioFormat::Flac);
        let args = build_args(
            Path::new("in.mp4"),
            Path::new("out.flac"),
            &spec,
            None,
            false,
        );
        let joined: Vec<String> = args
            .iter()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        assert!(!joined.iter().any(|a| a == "-b:a"));
        assert!(joined.contains(&"-n".to_string()));
    }

    #[test]
    fn force_uses_y() {
        let spec = format_spec(AudioFormat::Mp3);
        let args = build_args(
            Path::new("in.mkv"),
            Path::new("out.mp3"),
            &spec,
            Some(256),
            true,
        );
        let joined: Vec<String> = args
            .iter()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        assert!(joined.contains(&"-y".to_string()));
        assert!(joined.contains(&"256k".to_string()));
    }

    #[test]
    fn output_path_same_dir() {
        let out = output_path(Path::new("videos/clip.mp4"), None, "opus").unwrap();
        assert_eq!(out, PathBuf::from("videos/clip.opus"));
    }

    #[test]
    fn output_path_custom_dir() {
        let out = output_path(Path::new("clip.mp4"), Some(Path::new("out")), "m4a").unwrap();
        assert_eq!(out, PathBuf::from("out/clip.m4a"));
    }
}
