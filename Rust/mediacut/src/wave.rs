use crate::time::Time;
use anyhow::{bail, Context, Result};
use std::ffi::OsString;
use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};

/// Optional seek window for decoding / showwavespic.
#[derive(Debug, Clone, Copy, Default)]
pub struct TimeWindow {
    pub start: Option<Time>,
    pub end: Option<Time>,
    pub duration: Option<Time>,
}

impl TimeWindow {
    pub fn validate(self) -> Result<Self> {
        if self.end.is_some() && self.duration.is_some() {
            bail!("use either --end or --duration, not both");
        }
        if (self.end.is_some() || self.duration.is_some()) && self.start.is_none() {
            bail!("--end / --duration require --start");
        }
        if let (Some(start), Some(end)) = (self.start, self.end) {
            if end.as_secs() <= start.as_secs() {
                bail!("end ({end}) must be greater than start ({start})");
            }
        }
        if let Some(d) = self.duration {
            if d.as_secs() <= 0.0 {
                bail!("--duration must be positive");
            }
        }
        Ok(self)
    }

    fn push_seek_before_input(self, args: &mut Vec<OsString>) {
        if let Some(start) = self.start {
            args.push(OsString::from("-ss"));
            args.push(OsString::from(start.to_ffmpeg()));
        }
    }

    fn push_limit_after_input(self, args: &mut Vec<OsString>) {
        if let Some(dur) = self.duration {
            args.push(OsString::from("-t"));
            args.push(OsString::from(dur.to_ffmpeg()));
        } else if let (Some(start), Some(end)) = (self.start, self.end) {
            args.push(OsString::from("-t"));
            args.push(OsString::from(format!("{:.3}", end.as_secs() - start.as_secs())));
        }
    }
}

/// Per-column peak range in [-1, 1].
#[derive(Debug, Clone, Copy)]
pub struct PeakColumn {
    pub min: f32,
    pub max: f32,
}

/// Bucket mono f32 samples into `width` columns with min/max peaks.
pub fn bucket_peaks(samples: &[f32], width: usize) -> Vec<PeakColumn> {
    let width = width.max(1);
    if samples.is_empty() {
        return vec![PeakColumn { min: 0.0, max: 0.0 }; width];
    }
    let mut cols = Vec::with_capacity(width);
    let n = samples.len();
    for i in 0..width {
        let start = i * n / width;
        let end = ((i + 1) * n / width).max(start + 1).min(n);
        let slice = &samples[start..end];
        let mut min_v = f32::INFINITY;
        let mut max_v = f32::NEG_INFINITY;
        for &s in slice {
            min_v = min_v.min(s);
            max_v = max_v.max(s);
        }
        if !min_v.is_finite() {
            min_v = 0.0;
        }
        if !max_v.is_finite() {
            max_v = 0.0;
        }
        cols.push(PeakColumn {
            min: min_v.clamp(-1.0, 1.0),
            max: max_v.clamp(-1.0, 1.0),
        });
    }
    cols
}

/// Render peaks as a centered block waveform (`height` rows).
pub fn render_terminal(peaks: &[PeakColumn], height: usize) -> String {
    let height = height.max(2);
    let mut rows: Vec<String> = Vec::with_capacity(height);

    for row in 0..height {
        let mut line = String::with_capacity(peaks.len());
        // Amplitude axis: +1 at top, -1 at bottom
        let amp_hi = 1.0 - (2.0 * row as f32) / height as f32;
        let amp_lo = 1.0 - (2.0 * (row + 1) as f32) / height as f32;

        for col in peaks {
            let filled = col.max >= amp_lo && col.min <= amp_hi
                && !(col.max < amp_lo || col.min > amp_hi)
                && ranges_overlap(col.min, col.max, amp_lo, amp_hi);
            line.push(if filled { '█' } else { ' ' });
        }
        rows.push(line);
    }
    rows.join("\n")
}

fn ranges_overlap(a0: f32, a1: f32, b0: f32, b1: f32) -> bool {
    let (amin, amax) = if a0 <= a1 { (a0, a1) } else { (a1, a0) };
    let (bmin, bmax) = if b0 <= b1 { (b0, b1) } else { (b1, b0) };
    amin <= bmax && bmin <= amax
}

/// Build ffmpeg argv to decode mono f32le PCM to stdout (`-`).
pub fn build_pcm_args(input: &Path, window: TimeWindow) -> Vec<OsString> {
    let mut args: Vec<OsString> = vec![
        OsString::from("-hide_banner"),
        OsString::from("-loglevel"),
        OsString::from("error"),
    ];
    window.push_seek_before_input(&mut args);
    args.push(OsString::from("-i"));
    args.push(input.as_os_str().to_os_string());
    window.push_limit_after_input(&mut args);
    args.push(OsString::from("-vn"));
    args.push(OsString::from("-ac"));
    args.push(OsString::from("1"));
    args.push(OsString::from("-f"));
    args.push(OsString::from("f32le"));
    args.push(OsString::from("-"));
    args
}

/// Decode mono f32le samples via ffmpeg stdout.
pub fn decode_pcm_f32le(ffmpeg: &Path, input: &Path, window: TimeWindow) -> Result<Vec<f32>> {
    let args = build_pcm_args(input, window);
    let output = Command::new(ffmpeg)
        .args(&args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .with_context(|| format!("failed to start ffmpeg at {}", ffmpeg.display()))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        bail!("ffmpeg PCM decode failed: {stderr}");
    }

    let bytes = output.stdout;
    if bytes.len() % 4 != 0 {
        bail!(
            "ffmpeg returned truncated PCM ({} bytes, not multiple of 4)",
            bytes.len()
        );
    }
    if bytes.is_empty() {
        bail!("no audio samples decoded (missing audio stream?)");
    }

    let mut samples = Vec::with_capacity(bytes.len() / 4);
    for chunk in bytes.chunks_exact(4) {
        samples.push(f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]));
    }
    Ok(samples)
}

const PNG_BG: &str = "0x1a1a1a";
const PNG_FG: &str = "0x00d4aa";

/// Build ffmpeg argv for a static waveform PNG via `showwavespic`.
pub fn build_png_args(
    input: &Path,
    output: &Path,
    width: u32,
    height: u32,
    window: TimeWindow,
    force: bool,
) -> Vec<OsString> {
    let filter = format!(
        "color=c={PNG_BG}:s={width}x{height}[bg];\
         [0:a]aformat=channel_layouts=mono,showwavespic=s={width}x{height}:colors={PNG_FG}:scale=sqrt[fg];\
         [bg][fg]overlay=format=auto,format=rgb24"
    );

    let mut args: Vec<OsString> = vec![
        OsString::from("-hide_banner"),
        OsString::from("-loglevel"),
        OsString::from("error"),
        OsString::from(if force { "-y" } else { "-n" }),
    ];
    window.push_seek_before_input(&mut args);
    args.push(OsString::from("-i"));
    args.push(input.as_os_str().to_os_string());
    window.push_limit_after_input(&mut args);
    args.push(OsString::from("-filter_complex"));
    args.push(OsString::from(filter));
    args.push(OsString::from("-frames:v"));
    args.push(OsString::from("1"));
    args.push(output.as_os_str().to_os_string());
    args
}

/// Write terminal waveform to `out`.
pub fn print_terminal(peaks: &[PeakColumn], height: usize, out: &mut dyn Write) -> Result<()> {
    let text = render_terminal(peaks, height);
    writeln!(out, "{text}").context("failed to write terminal waveform")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bucket_empty_fills_zeros() {
        let cols = bucket_peaks(&[], 4);
        assert_eq!(cols.len(), 4);
        assert_eq!(cols[0].min, 0.0);
        assert_eq!(cols[0].max, 0.0);
    }

    #[test]
    fn bucket_constant() {
        let samples = vec![0.5_f32; 100];
        let cols = bucket_peaks(&samples, 10);
        assert_eq!(cols.len(), 10);
        for c in cols {
            assert!((c.min - 0.5).abs() < 1e-5);
            assert!((c.max - 0.5).abs() < 1e-5);
        }
    }

    #[test]
    fn bucket_span() {
        let mut samples = vec![0.0_f32; 100];
        samples[0] = -1.0;
        samples[99] = 1.0;
        let cols = bucket_peaks(&samples, 2);
        assert!(cols[0].min <= -0.9);
        assert!(cols[1].max >= 0.9);
    }

    #[test]
    fn render_nonempty() {
        let peaks = vec![
            PeakColumn { min: -0.5, max: 0.5 },
            PeakColumn { min: -1.0, max: 1.0 },
        ];
        let s = render_terminal(&peaks, 8);
        assert!(s.contains('█'));
        assert_eq!(s.lines().count(), 8);
    }

    #[test]
    fn png_args_contain_showwavespic() {
        let window = TimeWindow::default();
        let args = build_png_args(
            Path::new("in.mp3"),
            Path::new("out.png"),
            1280,
            240,
            window,
            true,
        );
        let joined: Vec<String> = args
            .iter()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        assert!(joined.iter().any(|a| a.contains("showwavespic")));
        assert!(joined.contains(&"-y".to_string()));
        assert!(joined.contains(&"out.png".to_string()));
    }

    #[test]
    fn pcm_args_mono_f32le() {
        let window = TimeWindow {
            start: Some(Time(1.0)),
            duration: Some(Time(2.0)),
            end: None,
        };
        let args = build_pcm_args(Path::new("in.mp3"), window);
        let joined: Vec<String> = args
            .iter()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        assert!(joined.contains(&"-ss".to_string()));
        assert!(joined.contains(&"-t".to_string()));
        assert!(joined.contains(&"f32le".to_string()));
        assert!(joined.contains(&"1".to_string())); // -ac 1
    }

    #[test]
    fn window_rejects_end_without_start() {
        let w = TimeWindow {
            start: None,
            end: Some(Time(5.0)),
            duration: None,
        };
        assert!(w.validate().is_err());
    }
}
