use anyhow::{bail, Result};
use std::fmt;

/// Timestamp in seconds (fractional allowed).
#[derive(Debug, Clone, Copy, PartialEq, PartialOrd)]
pub struct Time(pub f64);

impl Time {
    pub fn as_secs(self) -> f64 {
        self.0
    }

    /// Format for ffmpeg (`-ss` / `-to`): `HH:MM:SS.mmm` when needed.
    pub fn to_ffmpeg(self) -> String {
        let total = self.0.max(0.0);
        let hours = (total / 3600.0).floor() as u64;
        let minutes = ((total % 3600.0) / 60.0).floor() as u64;
        let secs = total % 60.0;
        if hours > 0 {
            format!("{hours}:{minutes:02}:{secs:06.3}")
        } else if minutes > 0 || total >= 60.0 {
            format!("{minutes}:{secs:06.3}")
        } else {
            format!("{secs:.3}")
        }
    }
}

impl fmt::Display for Time {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.to_ffmpeg())
    }
}

/// Half-open-ish cut interval `[start, end)` in seconds; `end` must be > `start`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Interval {
    pub start: Time,
    pub end: Time,
}

impl Interval {
    pub fn new(start: Time, end: Time) -> Result<Self> {
        if !(start.0.is_finite() && end.0.is_finite()) {
            bail!("times must be finite numbers");
        }
        if start.0 < 0.0 {
            bail!("start time must be >= 0 (got {})", start);
        }
        if end.0 <= start.0 {
            bail!("end ({end}) must be greater than start ({start})");
        }
        Ok(Self { start, end })
    }

    pub fn duration(self) -> f64 {
        self.end.0 - self.start.0
    }

    /// Parse `START-END` (e.g. `1:00-2:30`, `10-20.5`).
    pub fn parse_range(s: &str) -> Result<Self> {
        let s = s.trim();
        let (left, right) = split_range(s)?;
        let start = parse_time(left)?;
        let end = parse_time(right)?;
        Self::new(start, end)
    }
}

fn split_range(s: &str) -> Result<(&str, &str)> {
    // Prefer the last '-' that is not part of a negative (we disallow negatives anyway).
    // Ranges use START-END; times themselves use ':' so one '-' separator is enough.
    let Some(idx) = s.rfind('-') else {
        bail!("expected START-END range, got `{s}`");
    };
    if idx == 0 || idx + 1 >= s.len() {
        bail!("expected START-END range, got `{s}`");
    }
    Ok((&s[..idx], &s[idx + 1..]))
}

/// Parse `SS`, `MM:SS`, or `HH:MM:SS`, each part optionally fractional.
pub fn parse_time(s: &str) -> Result<Time> {
    let s = s.trim();
    if s.is_empty() {
        bail!("empty time string");
    }
    let parts: Vec<&str> = s.split(':').collect();
    if parts.len() > 3 {
        bail!("invalid time `{s}` (use SS, MM:SS, or HH:MM:SS)");
    }
    let mut values = Vec::with_capacity(parts.len());
    for part in &parts {
        if part.is_empty() {
            bail!("invalid time `{s}`");
        }
        let v: f64 = part
            .parse()
            .map_err(|_| anyhow::anyhow!("invalid time component `{part}` in `{s}`"))?;
        if !v.is_finite() || v < 0.0 {
            bail!("invalid time component `{part}` in `{s}`");
        }
        values.push(v);
    }
    let secs = match values.as_slice() {
        [s] => *s,
        [m, s] => m * 60.0 + s,
        [h, m, s] => h * 3600.0 + m * 60.0 + s,
        _ => bail!("invalid time `{s}`"),
    };
    Ok(Time(secs))
}

/// Sort intervals and reject any overlap (touching endpoints OK: end == next.start).
fn sort_by_start(intervals: &mut [Interval]) {
    intervals.sort_by(|a, b| {
        a.start
            .0
            .partial_cmp(&b.start.0)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
}

pub fn validate_non_overlapping(intervals: &[Interval]) -> Result<()> {
    let mut sorted = intervals.to_vec();
    sort_by_start(&mut sorted);
    for w in sorted.windows(2) {
        if w[0].end.0 > w[1].start.0 {
            bail!(
                "overlapping ranges: {}-{} and {}-{}",
                w[0].start,
                w[0].end,
                w[1].start,
                w[1].end
            );
        }
    }
    Ok(())
}

/// Given remove ranges and media duration, return complementary keep intervals.
pub fn keep_from_removes(removes: &[Interval], duration: f64) -> Result<Vec<Interval>> {
    if duration <= 0.0 || !duration.is_finite() {
        bail!("media duration must be positive (got {duration})");
    }
    validate_non_overlapping(removes)?;

    let mut sorted = removes.to_vec();
    sorted.sort_by(|a, b| {
        a.start
            .0
            .partial_cmp(&b.start.0)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    for r in &sorted {
        if r.start.0 >= duration {
            bail!(
                "remove range starts at or after end of media ({r_start} >= {duration})",
                r_start = r.start
            );
        }
        if r.end.0 > duration {
            bail!(
                "remove range ends after media duration ({} > {duration})",
                r.end
            );
        }
    }

    let mut keeps = Vec::new();
    let mut cursor = 0.0_f64;
    for r in &sorted {
        if r.start.0 > cursor {
            keeps.push(Interval::new(Time(cursor), r.start)?);
        }
        cursor = cursor.max(r.end.0);
    }
    if cursor < duration {
        keeps.push(Interval::new(Time(cursor), Time(duration))?);
    }
    if keeps.is_empty() {
        bail!("nothing left to keep after removals");
    }
    Ok(keeps)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_seconds() {
        assert_eq!(parse_time("12").unwrap().0, 12.0);
        assert_eq!(parse_time("12.5").unwrap().0, 12.5);
    }

    #[test]
    fn parse_mm_ss() {
        assert_eq!(parse_time("1:02").unwrap().0, 62.0);
        assert_eq!(parse_time("1:02.5").unwrap().0, 62.5);
    }

    #[test]
    fn parse_hh_mm_ss() {
        assert_eq!(parse_time("1:02:03").unwrap().0, 3723.0);
    }

    #[test]
    fn parse_range_ok() {
        let i = Interval::parse_range("1:00-2:30").unwrap();
        assert_eq!(i.start.0, 60.0);
        assert_eq!(i.end.0, 150.0);
    }

    #[test]
    fn reject_inverted() {
        assert!(Interval::new(Time(10.0), Time(5.0)).is_err());
    }

    #[test]
    fn overlap_rejected() {
        let a = Interval::new(Time(0.0), Time(10.0)).unwrap();
        let b = Interval::new(Time(5.0), Time(15.0)).unwrap();
        assert!(validate_non_overlapping(&[a, b]).is_err());
    }

    #[test]
    fn touching_ok() {
        let a = Interval::new(Time(0.0), Time(10.0)).unwrap();
        let b = Interval::new(Time(10.0), Time(15.0)).unwrap();
        assert!(validate_non_overlapping(&[a, b]).is_ok());
    }

    #[test]
    fn remove_middle() {
        let rem = Interval::new(Time(10.0), Time(20.0)).unwrap();
        let keeps = keep_from_removes(&[rem], 30.0).unwrap();
        assert_eq!(keeps.len(), 2);
        assert_eq!(keeps[0].start.0, 0.0);
        assert_eq!(keeps[0].end.0, 10.0);
        assert_eq!(keeps[1].start.0, 20.0);
        assert_eq!(keeps[1].end.0, 30.0);
    }

    #[test]
    fn remove_start_and_end() {
        let a = Interval::new(Time(0.0), Time(5.0)).unwrap();
        let b = Interval::new(Time(25.0), Time(30.0)).unwrap();
        let keeps = keep_from_removes(&[a, b], 30.0).unwrap();
        assert_eq!(keeps.len(), 1);
        assert_eq!(keeps[0].start.0, 5.0);
        assert_eq!(keeps[0].end.0, 25.0);
    }

    #[test]
    fn ffmpeg_format() {
        assert_eq!(Time(5.5).to_ffmpeg(), "5.500");
        assert_eq!(Time(65.0).to_ffmpeg(), "1:05.000");
        assert_eq!(Time(3723.25).to_ffmpeg(), "1:02:03.250");
    }
}
