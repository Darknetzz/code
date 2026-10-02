use serde::{Deserialize, Serialize};

use crate::models::ReportFormat;

pub const GUI_PREFS_KEY: &str = "rust_sizetree_gui_prefs";

fn default_folders_first() -> bool {
    true
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GuiPrefs {
    pub show_share: bool,
    pub show_size: bool,
    pub show_percent: bool,
    pub show_files: bool,
    pub show_dirs: bool,
    /// Always list directories before files when sorting (any column).
    #[serde(default = "default_folders_first")]
    pub folders_first: bool,
    pub report_format: ReportFormat,
    pub report_limit: usize,
    pub open_html_after_save: bool,
}

impl Default for GuiPrefs {
    fn default() -> Self {
        Self {
            show_share: true,
            show_size: true,
            show_percent: true,
            show_files: true,
            show_dirs: true,
            folders_first: default_folders_first(),
            report_format: ReportFormat::Html,
            report_limit: 50,
            open_html_after_save: true,
        }
    }
}
