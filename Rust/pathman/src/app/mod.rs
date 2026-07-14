#[allow(unused_imports)]
use crate::config::AppConfig;
#[allow(unused_imports)]
use crate::env_model::EnvEntry;
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
pub enum AppMode {
    #[default]
    Path,
    Environment,
}

#[derive(Clone, Copy, PartialEq, Eq, Default)]
pub enum Scope {
    User,
    System,
    /// Merged machine + user view (editable). Default: full PATH picture and cross-store editing.
    #[default]
    Effective,
}

pub struct PathmanApp {
    mode: AppMode,
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
    /// Environment mode: merged segments when Effective scope is active.
    env_segments: Vec<(PathOrigin, EnvEntry)>,
    /// Environment mode: flat list for User/System scopes.
    env_entries: Vec<EnvEntry>,
    env_user_baseline: std::collections::HashMap<String, String>,
    env_system_baseline: std::collections::HashMap<String, String>,
    env_dirty: bool,
    env_list_search: String,
    confirm_remove_env: Option<usize>,
    show_confirm_env_system: bool,
    env_show_change_summary: bool,
    env_change_summary_text: String,
    env_pending_saved_feedback: bool,
    env_saved_feedback_until: Option<f64>,
    env_show_confirm_discard: bool,
    /// Variable names locked after load or first successful validation.
    env_locked_names: std::collections::HashSet<String>,
    show_confirm_mode_switch: bool,
    pending_mode_switch: Option<AppMode>,
    path_sort: Option<(column_sort::PathSortColumn, column_sort::SortDir)>,
    env_sort: Option<(column_sort::EnvSortColumn, column_sort::SortDir)>,
}

#[derive(Clone, PartialEq, Eq)]
pub(crate) enum DuplicateViewFilter {
    PathDuplicate { key: String, banner: String },
    MissingPaths,
    /// Rows that show a duplicate mark: cross-store and/or repeated within the same store.
    OnlyDuplicates,
}

mod column_sort;
mod env_panel;
mod helpers;
mod impls;
mod path_panel;
