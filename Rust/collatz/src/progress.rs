use std::io::{self, IsTerminal, Write};

const DISPLAY_MAX_LEN: usize = 48;

pub struct ProgressReporter {
    enabled: bool,
    interactive: bool,
    last_reported: u64,
    updates_since_flush: u32,
    finished: bool,
}

impl ProgressReporter {
    pub fn new(enabled: bool) -> Self {
        Self {
            enabled,
            interactive: io::stderr().is_terminal(),
            last_reported: 0,
            updates_since_flush: 0,
            finished: false,
        }
    }

    pub fn should_report_step(&self, steps: u64) -> bool {
        self.enabled && self.should_report(steps)
    }

    fn should_report(&self, steps: u64) -> bool {
        if steps == 0 {
            return false;
        }

        let interval = if self.interactive {
            match steps {
                1..=999 => 10,
                1_000..=99_999 => 100,
                100_000..=9_999_999 => 1_000,
                _ => 10_000,
            }
        } else {
            match steps {
                1..=9_999 => 1_000,
                _ => 10_000,
            }
        };

        steps.saturating_sub(self.last_reported) >= interval
    }

    pub fn status(&self, message: &str) {
        status_line(message);
    }

    pub fn on_step_u128(&mut self, steps: u64, current: u128, peak: u128) {
        if !self.should_report(steps) {
            return;
        }

        self.last_reported = steps;
        self.write_line(&format!(
            "step {steps:>8}  current {current:<DISPLAY_MAX_LEN$}  peak {peak}"
        ));
    }

    pub fn on_step_big(&mut self, steps: u64, current_bits: u64, peak_bits: u64) {
        if !self.should_report(steps) {
            return;
        }

        self.last_reported = steps;
        self.write_line(&format!(
            "step {steps:>8}  current ~{current_bits} bits  peak ~{peak_bits} bits"
        ));
    }

    fn write_line(&mut self, line: &str) {
        if self.interactive {
            eprint!("\r{line}");
        } else {
            eprintln!("{line}");
        }

        self.updates_since_flush += 1;
        if self.updates_since_flush >= 8 {
            self.flush_stderr();
        }
    }

    fn flush_stderr(&mut self) {
        let _ = io::stderr().flush();
        self.updates_since_flush = 0;
    }

    pub fn finish(&mut self) {
        if self.enabled && !self.finished {
            self.finished = true;
            self.flush_stderr();
            if self.interactive {
                eprintln!();
            }
        }
    }
}

impl Drop for ProgressReporter {
    fn drop(&mut self) {
        self.finish();
    }
}

pub fn status_line(message: &str) {
    eprintln!("{message}");
    let _ = io::stderr().flush();
}

pub fn progress_enabled_by_default(json: bool) -> bool {
    !json && io::stderr().is_terminal()
}
