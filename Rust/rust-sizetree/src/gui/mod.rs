mod app;
mod disk;
mod entry_icons;
mod prefs;

use std::path::PathBuf;

use anyhow::{bail, Result};

use crate::scan::ScanOptions;

/// Launch the native SizeTree window.
pub fn run_gui(path: PathBuf, opts: ScanOptions) -> Result<u8> {
    let target = path.canonicalize().unwrap_or(path);
    if !target.is_dir() {
        bail!("not a directory: {}", target.display());
    }

    let native_options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1280.0, 800.0])
            .with_min_inner_size([900.0, 560.0])
            .with_title("rust-sizetree"),
        ..Default::default()
    };

    eframe::run_native(
        "rust-sizetree",
        native_options,
        Box::new(move |cc| Ok(Box::new(app::SizeTreeApp::new(cc, target, opts)))),
    )
    .map_err(|e| anyhow::anyhow!("GUI error: {e}"))?;
    Ok(0)
}
