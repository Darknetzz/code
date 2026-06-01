#[allow(unused_imports)]
use crate::config::AppConfig;
#[allow(unused_imports)]
use crate::path_model::{self, PathOrigin};
#[allow(unused_imports)]
use eframe::egui;
#[allow(unused_imports)]
use eframe::egui::scroll_area::ScrollBarVisibility;
#[allow(unused_imports)]
use eframe::egui::{ScrollArea, Sense, TextEdit};
#[allow(unused_imports)]
use crate::row_icons::{
    mix_srgb, path_add_origin_menu, path_add_toolbar_button, path_row_icon_button,
    path_top_bar_button, path_top_bar_selectable, AddToolbarIcon, PathRowIcon, TopBarButtonEmphasis,
    TopBarIcon,
};

#[derive(Clone, Copy, PartialEq, Eq, Default)]
pub enum Scope {
    User,
    System,
    /// Merged machine + user view (editable). Default: full PATH picture and cross-store editing.
    #[default]
    Effective,
}

pub struct PathmanApp {
    scope: Scope,
    entries: Vec<String>,
    /// Editable merged PATH when [`Scope::Effective`] is active.
    effective_segments: Vec<(PathOrigin, String)>,
    /// Machine PATH join at last effective load; used to detect machine-store edits for confirm/UAC.
    baseline_machine_join: String,
    dirty: bool,
    status: String,
    status_err: bool,
    config: AppConfig,
    show_confirm_system: bool,
    /// Row index pending removal confirmation (`X` clicked).
    confirm_remove_index: Option<usize>,
    /// Confirm before running adjacent dedupe from the toolbar.
    show_confirm_dedupe: bool,
    /// Confirm before discarding unsaved edits (reload from disk).
    show_confirm_discard: bool,
    warn_missing: bool,
    /// Unix: show shell file path editor
    shell_path_edit: String,
    show_shell_settings: bool,
    /// System + user duplicate report (read from disk).
    show_duplicate_tool: bool,
    /// List shows only rows matching the clicked mark (duplicate group or missing paths).
    duplicate_view_filter: Option<DuplicateViewFilter>,
    /// Substring filter for the PATH entry list (case-insensitive; matches raw or expanded path).
    list_search: String,
    /// Summary of edits vs on-disk PATH (`Changes…`).
    show_change_summary: bool,
    change_summary_text: String,
    /// Set when a save succeeded; next `update` turns this into [`Self::saved_feedback_until`].
    pending_saved_feedback: bool,
    /// Show green "Saved" in the toolbar until this egui time (seconds).
    saved_feedback_until: Option<f64>,
}

#[derive(Clone, PartialEq, Eq)]
pub(crate) enum DuplicateViewFilter {
    PathDuplicate { key: String, banner: String },
    MissingPaths,
    /// Rows that show a duplicate mark: cross-store and/or repeated within the same store.
    OnlyDuplicates,
}

mod helpers;
mod impls;
