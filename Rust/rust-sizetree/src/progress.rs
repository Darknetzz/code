use std::io::{self, Write};
use std::time::{Duration, Instant};

use crate::models::{format_count, format_size, ScanStats};

/// Throttled stderr progress line (mirrors pytree's Rich progress summary).
pub struct ScanProgress {
    last_tick: Instant,
    interval: Duration,
}

impl ScanProgress {
    pub fn new() -> Self {
        Self {
            last_tick: Instant::now() - Duration::from_secs(1),
            interval: Duration::from_millis(120),
        }
    }

    pub fn notify(&mut self, stats: &ScanStats) {
        let now = Instant::now();
        if now.duration_since(self.last_tick) < self.interval {
            return;
        }
        self.last_tick = now;
        let current = stats
            .current
            .as_deref()
            .map(|p| format!(" — {p}"))
            .unwrap_or_default();
        let line = format!(
            "\rScanning…  {} files  {} dirs  {}{}   ",
            format_count(stats.files),
            format_count(stats.dirs),
            format_size(stats.size),
            current
        );
        let _ = io::stderr().write_all(line.as_bytes());
        let _ = io::stderr().flush();
    }

    pub fn finish(&self, stats: &ScanStats) {
        let _ = writeln!(
            io::stderr(),
            "\rScanned  {} files  {} dirs  {}   ",
            format_count(stats.files),
            format_count(stats.dirs),
            format_size(stats.size),
        );
    }
}
