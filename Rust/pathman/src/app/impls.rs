use super::*;
use super::helpers::*;
use std::path::PathBuf;

use super::AppMode;

impl PathmanApp {
    pub fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        let (config, config_err) = AppConfig::load_with_status();
        let shell_path_edit = config
            .user_shell_path
            .clone()
            .unwrap_or_else(|| {
                config
                    .resolved_user_shell_path()
                    .to_string_lossy()
                    .to_string()
            });
        let mut app = Self {
            mode: AppMode::default(),
            scope: Scope::default(),
            entries: Vec::new(),
            effective_segments: Vec::new(),
            baseline_machine_join: String::new(),
            dirty: false,
            status: String::new(),
            status_err: false,
            config,
            show_confirm_system: false,
            confirm_remove_index: None,
            show_confirm_dedupe: false,
            show_confirm_discard: false,
            warn_missing: true,
            shell_path_edit,
            show_shell_settings: false,
            show_duplicate_tool: false,
            duplicate_view_filter: None,
            list_search: String::new(),
            show_change_summary: false,
            change_summary_text: String::new(),
            pending_saved_feedback: false,
            saved_feedback_until: None,
            env_segments: Vec::new(),
            env_entries: Vec::new(),
            env_user_baseline: std::collections::HashMap::new(),
            env_system_baseline: std::collections::HashMap::new(),
            env_dirty: false,
            env_list_search: String::new(),
            confirm_remove_env: None,
            show_confirm_env_system: false,
            env_show_change_summary: false,
            env_change_summary_text: String::new(),
            env_pending_saved_feedback: false,
            env_saved_feedback_until: None,
            env_show_confirm_discard: false,
            env_locked_names: std::collections::HashSet::new(),
            show_confirm_mode_switch: false,
            pending_mode_switch: None,
            path_sort: None,
            env_sort: None,
        };
        app.reload_from_store();
        if let Some(msg) = config_err {
            app.set_status_err(format!("Could not read pathman.toml (using defaults): {msg}"));
        }
        app
    }

    pub(crate) fn reload_from_store(&mut self) {
        match self.mode {
            AppMode::Path => self.reload_path_from_store(),
            AppMode::Environment => self.reload_env_from_store(),
        }
    }

    fn reload_path_from_store(&mut self) {
        self.confirm_remove_index = None;
        self.show_confirm_dedupe = false;
        self.show_confirm_discard = false;
        self.show_duplicate_tool = false;
        self.saved_feedback_until = None;
        self.duplicate_view_filter = None;
        self.list_search.clear();
        self.show_change_summary = false;
        self.path_sort = None;
        self.status_clear();
        let r = match self.scope {
            Scope::User => self.load_user(),
            Scope::System => self.load_system(),
            Scope::Effective => self.load_effective(),
        };
        if let Err(e) = r {
            self.set_status_err(format!("Load failed: {e:#}"));
        }
    }

    /// Fresh machine + user PATH entries from disk (for duplicate report).
    fn read_stores_for_duplicate_report(&self) -> anyhow::Result<(Vec<String>, Vec<String>)> {
        #[cfg(windows)]
        {
            Ok((
                path_model::split(&crate::persist::read_machine_path()?),
                path_model::split(&crate::persist::read_user_path()?),
            ))
        }
        #[cfg(not(windows))]
        {
            Ok((
                crate::persist::read_system_entries()?,
                crate::persist::read_user_entries(&self.config)?,
            ))
        }
    }

    pub(crate) fn read_machine_slice_for_marks(&self) -> Vec<String> {
        #[cfg(windows)]
        {
            path_model::split(
                &crate::persist::read_machine_path().unwrap_or_default(),
            )
        }
        #[cfg(not(windows))]
        {
            crate::persist::read_system_entries().unwrap_or_default()
        }
    }

    pub(crate) fn read_user_slice_for_marks(&self) -> Vec<String> {
        #[cfg(windows)]
        {
            path_model::split(&crate::persist::read_user_path().unwrap_or_default())
        }
        #[cfg(not(windows))]
        {
            crate::persist::read_user_entries(&self.config).unwrap_or_default()
        }
    }

    fn row_passes_duplicate_filter(&self, path_str: &str, is_marked_duplicate: bool) -> bool {
        match &self.duplicate_view_filter {
            None => true,
            Some(DuplicateViewFilter::OnlyDuplicates) => is_marked_duplicate,
            Some(DuplicateViewFilter::PathDuplicate { key, .. }) => {
                let k = path_model::path_duplicate_key(path_str);
                !k.is_empty() && k == *key
            }
            Some(DuplicateViewFilter::MissingPaths) => !path_model::entry_exists(path_str),
        }
    }

    fn entry_matches_list_search(&self, raw_path: &str) -> bool {
        let q = self.list_search.trim();
        if q.is_empty() {
            return true;
        }
        let ql = q.to_lowercase();
        if raw_path.to_lowercase().contains(&ql) {
            return true;
        }
        path_model::expanded_path(raw_path)
            .to_lowercase()
            .contains(&ql)
    }

    /// Row is shown in the list: duplicate/missing filters and search box.
    pub(crate) fn row_visible_in_path_list(&self, path_str: &str, is_marked_duplicate: bool) -> bool {
        self.row_passes_duplicate_filter(path_str, is_marked_duplicate)
            && self.entry_matches_list_search(path_str)
    }

    pub(crate) fn toggle_path_duplicate_filter(&mut self, key: String, banner: String) {
        match &self.duplicate_view_filter {
            Some(DuplicateViewFilter::PathDuplicate { key: k, .. }) if k == &key => {
                self.duplicate_view_filter = None;
            }
            _ => {
                self.duplicate_view_filter = Some(DuplicateViewFilter::PathDuplicate { key, banner });
            }
        }
    }

    pub(crate) fn toggle_missing_path_filter(&mut self) {
        match self.duplicate_view_filter {
            Some(DuplicateViewFilter::MissingPaths) => self.duplicate_view_filter = None,
            _ => self.duplicate_view_filter = Some(DuplicateViewFilter::MissingPaths),
        }
    }

    fn toggle_only_duplicates_filter(&mut self) {
        match self.duplicate_view_filter {
            Some(DuplicateViewFilter::OnlyDuplicates) => self.duplicate_view_filter = None,
            _ => self.duplicate_view_filter = Some(DuplicateViewFilter::OnlyDuplicates),
        }
    }

    /// After filtering by duplicate PATH key from User or System tab, show the merged list.
    pub(crate) fn switch_to_effective_for_path_dup_filter(&mut self) {
        if !matches!(
            &self.duplicate_view_filter,
            Some(DuplicateViewFilter::PathDuplicate { .. })
        ) {
            return;
        }
        if !matches!(self.scope, Scope::User | Scope::System) {
            return;
        }
        let prev = self.scope;
        self.scope = Scope::Effective;
        if let Err(e) = self.load_effective() {
            self.set_status_err(format!("Could not load Effective view: {e:#}"));
            self.scope = prev;
        }
    }

    fn load_user(&mut self) -> anyhow::Result<()> {
        #[cfg(windows)]
        {
            let s = crate::persist::read_user_path()?;
            self.entries = path_model::split(&s);
        }
        #[cfg(not(windows))]
        {
            self.entries = crate::persist::read_user_entries(&self.config)?;
        }
        self.dirty = false;
        Ok(())
    }

    fn load_system(&mut self) -> anyhow::Result<()> {
        #[cfg(windows)]
        {
            let s = crate::persist::read_machine_path()?;
            self.entries = path_model::split(&s);
        }
        #[cfg(not(windows))]
        {
            self.entries = crate::persist::read_system_entries()?;
        }
        self.dirty = false;
        Ok(())
    }

    fn load_effective(&mut self) -> anyhow::Result<()> {
        #[cfg(windows)]
        {
            let m = path_model::split(&crate::persist::read_machine_path()?);
            let u = path_model::split(&crate::persist::read_user_path()?);
            self.baseline_machine_join = path_model::join(&m);
            self.effective_segments = path_model::merge_machine_user_preview_style(&m, &u);
        }
        #[cfg(not(windows))]
        {
            // Same ordering as Windows HKLM then HKCU: pathman system store, then user shell block.
            // A login shell’s real PATH can include extra sources; this view edits only those two stores.
            let m = crate::persist::read_system_entries()?;
            let u = crate::persist::read_user_entries(&self.config)?;
            self.baseline_machine_join = path_model::join(&m);
            self.effective_segments = path_model::merge_machine_user_preview_style(&m, &u);
        }
        self.dirty = false;
        Ok(())
    }

    fn save(&mut self) {
        self.status_clear();
        let res = match self.scope {
            Scope::User => {
                let entries = path_model::dedupe_adjacent(&self.entries);
                self.entries = entries.clone();
                self.save_user(&entries)
            }
            Scope::System => {
                let entries = path_model::dedupe_adjacent(&self.entries);
                self.entries = entries.clone();
                self.save_system(&entries)
            }
            Scope::Effective => {
                let mut segs = self.effective_segments.clone();
                path_model::dedupe_adjacent_tagged(&mut segs);
                self.effective_segments = segs.clone();
                let (machine, user) = path_model::split_origins(&segs);
                let machine_join = path_model::join(&machine);
                // Unix (and our stores): never write an empty system snippet — but user-only edits
                // are common; skip the system write when nothing was on disk and remains empty.
                let skip_system_write =
                    machine_join.is_empty() && self.baseline_machine_join.is_empty();
                self.save_user(&user).and_then(|_| {
                    if skip_system_write {
                        Ok(())
                    } else {
                        self.save_system(&machine)
                    }
                })
            }
        };
        match res {
            Ok(()) => {
                self.dirty = false;
                let reload = match self.scope {
                    Scope::User => self.load_user(),
                    Scope::System => self.load_system(),
                    Scope::Effective => self.load_effective(),
                };
                match reload {
                    Ok(()) => {
                        self.set_status_ok("Saved. Open a new terminal for changes to apply.".into());
                        self.pending_saved_feedback = true;
                    }
                    Err(e) => self.set_status_err(format!(
                        "Save succeeded but reload from disk failed: {e:#}"
                    )),
                }
            }
            Err(e) => self.set_status_err(format!("Save failed: {e:#}")),
        }
    }

    /// True if saving would change the machine/system PATH string (needs confirm / elevation on Windows).
    fn effective_machine_save_pending_confirm(&self) -> bool {
        let mut segs = self.effective_segments.clone();
        path_model::dedupe_adjacent_tagged(&mut segs);
        let (m, _) = path_model::split_origins(&segs);
        path_model::join(&m) != self.baseline_machine_join
    }

    fn save_user(&mut self, entries: &[String]) -> anyhow::Result<()> {
        #[cfg(windows)]
        {
            let joined = path_model::join(entries);
            let prev = crate::persist::read_user_path().unwrap_or_default();
            let _ = crate::persist::backup_path(
                "windows-user",
                &prev,
                &backup_dir_win(),
            );
            crate::persist::write_user_path(&joined)?;
        }
        #[cfg(not(windows))]
        {
            let path = self.config.resolved_user_shell_path();
            let prev = std::fs::read_to_string(&path).unwrap_or_default();
            let _ = crate::persist::backup_string("unix-user", &prev);
            crate::persist::write_user_entries(&self.config, entries)?;
        }
        Ok(())
    }

    fn save_system(&mut self, entries: &[String]) -> anyhow::Result<()> {
        #[cfg(windows)]
        {
            let joined = path_model::join(entries);
            let prev = crate::persist::read_machine_path().unwrap_or_default();
            let _ = crate::persist::backup_path(
                "windows-machine",
                &prev,
                &backup_dir_win(),
            );
            crate::persist::request_elevated_machine_path(&joined)?;
        }
        #[cfg(not(windows))]
        {
            let prev = read_unix_system_file_raw()?;
            let _ = crate::persist::backup_string("unix-system", &prev);
            crate::persist::write_system_entries(entries)?;
        }
        Ok(())
    }

    pub(crate) fn status_clear(&mut self) {
        self.status.clear();
        self.status_err = false;
    }

    pub(crate) fn set_status_ok(&mut self, s: String) {
        self.status = s;
        self.status_err = false;
    }

    pub(crate) fn set_status_err(&mut self, s: String) {
        self.status = s;
        self.status_err = true;
    }

    /// Open the expanded path in the system file manager (Explorer, Finder, xdg-open, …).
    pub(crate) fn open_entry_directory(&mut self, raw_path: &str) {
        let expanded = path_model::expanded_path(raw_path);
        let t = expanded.trim();
        if t.is_empty() {
            self.set_status_err("Cannot open: path is empty.".into());
            return;
        }
        match open::that(t) {
            Ok(()) => self.status_clear(),
            Err(e) => self.set_status_err(format!("Could not open location: {e}")),
        }
    }

    fn read_disk_user(&self) -> anyhow::Result<Vec<String>> {
        #[cfg(windows)]
        {
            Ok(path_model::split(&crate::persist::read_user_path()?))
        }
        #[cfg(not(windows))]
        {
            crate::persist::read_user_entries(&self.config)
        }
    }

    fn read_disk_machine(&self) -> anyhow::Result<Vec<String>> {
        #[cfg(windows)]
        {
            Ok(path_model::split(&crate::persist::read_machine_path()?))
        }
        #[cfg(not(windows))]
        {
            crate::persist::read_system_entries()
        }
    }

    /// Human-readable diff of the current editor state vs PATH read from disk (same shape as Save).
    fn compute_change_summary(&self) -> String {
        let inner = || -> anyhow::Result<String> {
            let mut out = String::from(
                "Compared to what is saved on disk right now (nothing is written until you click Save):\n\n",
            );
            match self.scope {
                Scope::User => {
                    let disk = path_model::dedupe_adjacent(&self.read_disk_user()?);
                    let pending = path_model::dedupe_adjacent(&self.entries);
                    out.push_str(&format_path_store_diff("User PATH", &disk, &pending));
                }
                Scope::System => {
                    let disk = path_model::dedupe_adjacent(&self.read_disk_machine()?);
                    let pending = path_model::dedupe_adjacent(&self.entries);
                    out.push_str(&format_path_store_diff(
                        "Machine (system) PATH",
                        &disk,
                        &pending,
                    ));
                }
                Scope::Effective => {
                    let dm = path_model::dedupe_adjacent(&self.read_disk_machine()?);
                    let du = path_model::dedupe_adjacent(&self.read_disk_user()?);
                    let mut segs = self.effective_segments.clone();
                    path_model::dedupe_adjacent_tagged(&mut segs);
                    let (pm, pu) = path_model::split_origins(&segs);
                    out.push_str(&format_path_store_diff(
                        "Machine (system) PATH",
                        &dm,
                        &pm,
                    ));
                    out.push_str(&format_path_store_diff("User PATH", &du, &pu));
                }
            }
            Ok(out)
        };
        match inner() {
            Ok(s) => s,
            Err(e) => format!("Could not read PATH from disk to compare:\n{e:#}"),
        }
    }

    fn apply_remove_row(&mut self, i: usize) {
        match self.scope {
            Scope::Effective => {
                if i < self.effective_segments.len() {
                    self.effective_segments.remove(i);
                    self.dirty = true;
                }
            }
            Scope::User | Scope::System => {
                if i < self.entries.len() {
                    self.entries.remove(i);
                    self.dirty = true;
                }
            }
        }
    }

    /// Remove row immediately or open confirmation per [`AppConfig::skip_remove_confirmation`].
    pub(crate) fn request_remove_row(&mut self, i: usize) {
        if self.config.skip_remove_confirmation {
            self.apply_remove_row(i);
        } else {
            self.confirm_remove_index = Some(i);
        }
    }

    fn apply_config_shell_path(&mut self) {
        let p = self.shell_path_edit.trim();
        if p.is_empty() {
            self.config.user_shell_path = None;
        } else {
            self.config.user_shell_path = Some(p.to_string());
        }
        if let Err(e) = self.config.save() {
            self.set_status_err(format!("Config save: {e:#}"));
            return;
        }
        self.set_status_ok("Shell file path saved to pathman.toml.".into());
        if self.mode == AppMode::Environment {
            match self.scope {
                Scope::User | Scope::Effective => {
                    self.reload_env_from_store();
                }
                Scope::System => {}
            }
        } else {
            match self.scope {
                Scope::User => {
                    let _ = self.load_user();
                }
                Scope::Effective => {
                    let _ = self.load_effective();
                }
                Scope::System => {}
            }
        }
    }
}

#[cfg(windows)]
fn backup_dir_win() -> PathBuf {
    let mut d = dirs::config_dir().unwrap_or_else(|| PathBuf::from("."));
    d.push("pathman");
    d.push("backups");
    d
}

#[cfg(not(windows))]
fn read_unix_system_file_raw() -> anyhow::Result<String> {
    #[cfg(target_os = "macos")]
    let p = std::path::Path::new("/etc/paths.d/99-pathman");
    #[cfg(not(target_os = "macos"))]
    let p = std::path::Path::new("/etc/profile.d/pathman.sh");
    if p.exists() {
        Ok(std::fs::read_to_string(p)?)
    } else {
        Ok(String::new())
    }
}

impl eframe::App for PathmanApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        if self.pending_saved_feedback {
            self.pending_saved_feedback = false;
            self.saved_feedback_until = Some(ctx.input(|i| i.time) + 2.0);
        }
        if self.env_pending_saved_feedback {
            self.env_pending_saved_feedback = false;
            self.env_saved_feedback_until = Some(ctx.input(|i| i.time) + 2.0);
        }

        egui::TopBottomPanel::top("top").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("pathman");
                let subtitle = match self.mode {
                    AppMode::Path => "PATH editor",
                    AppMode::Environment => "Environment variables",
                };
                ui.label(egui::RichText::new(subtitle).weak());
            });
            ui.scope(|ui| {
                let s = &mut ui.style_mut().spacing;
                let min_h = 26.0_f32;
                s.interact_size.y = s.interact_size.y.max(min_h);
                s.button_padding = egui::vec2(10.0, 6.0);
                ui.horizontal(|ui| {
                    if path_top_bar_selectable(
                        ui,
                        self.mode == AppMode::Path,
                        "PATH",
                        TopBarIcon::ScopeEffective,
                    )
                    .clicked()
                    {
                        self.request_mode_switch(AppMode::Path);
                    }
                    if path_top_bar_selectable(
                        ui,
                        self.mode == AppMode::Environment,
                        "Environment",
                        TopBarIcon::ScopeUser,
                    )
                    .clicked()
                    {
                        self.request_mode_switch(AppMode::Environment);
                    }
                    ui.separator();
                if path_top_bar_selectable(
                    ui,
                    self.scope == Scope::Effective,
                    "Effective",
                    TopBarIcon::ScopeEffective,
                )
                .clicked()
                {
                    self.scope = Scope::Effective;
                    self.reload_from_store();
                }
                if path_top_bar_selectable(
                    ui,
                    self.scope == Scope::User,
                    "User",
                    TopBarIcon::ScopeUser,
                )
                .clicked()
                {
                    self.scope = Scope::User;
                    self.reload_from_store();
                }
                if path_top_bar_selectable(
                    ui,
                    self.scope == Scope::System,
                    "System",
                    TopBarIcon::ScopeSystem,
                )
                .clicked()
                {
                    self.scope = Scope::System;
                    self.reload_from_store();
                }
                ui.separator();
                if path_top_bar_button(
                    ui,
                    "Reload",
                    TopBarIcon::Reload,
                    true,
                    0.0,
                    Some("Reload from disk (keeps unsaved edits unless you discard first)."),
                    TopBarButtonEmphasis::Info,
                )
                .clicked()
                {
                    self.reload_from_store();
                }
                let mode_dirty = self.is_mode_dirty();
                let save_emphasis = if mode_dirty {
                    TopBarButtonEmphasis::Unsaved
                } else {
                    TopBarButtonEmphasis::IdlePrimary
                };
                let save_clicked = path_top_bar_button(
                    ui,
                    "Save",
                    TopBarIcon::Save,
                    mode_dirty,
                    72.0,
                    Some("Write the current list to disk (enabled when there are unsaved changes)."),
                    save_emphasis,
                )
                .clicked();
                let needs_confirm = match self.mode {
                    AppMode::Path => {
                        matches!(self.scope, Scope::System)
                            || (self.scope == Scope::Effective
                                && self.effective_machine_save_pending_confirm())
                    }
                    AppMode::Environment => {
                        matches!(self.scope, Scope::System)
                            || (self.scope == Scope::Effective
                                && self.effective_env_machine_save_pending_confirm())
                    }
                };
                let do_save = save_clicked
                    && if needs_confirm {
                        match self.mode {
                            AppMode::Path => self.show_confirm_system = true,
                            AppMode::Environment => self.show_confirm_env_system = true,
                        }
                        false
                    } else {
                        true
                    };
                if do_save {
                    match self.mode {
                        AppMode::Path => self.save(),
                        AppMode::Environment => self.save_env(),
                    }
                }
                if path_top_bar_button(
                    ui,
                    "Discard",
                    TopBarIcon::Discard,
                    mode_dirty,
                    0.0,
                    Some("Discard all unsaved changes and reload from disk."),
                    TopBarButtonEmphasis::Danger,
                )
                .clicked()
                {
                    match self.mode {
                        AppMode::Path => self.show_confirm_discard = true,
                        AppMode::Environment => self.env_show_confirm_discard = true,
                    }
                }
                let now = ctx.input(|i| i.time);
                let show_saved_badge = !mode_dirty
                    && match self.mode {
                        AppMode::Path => self
                            .saved_feedback_until
                            .is_some_and(|until| now < until),
                        AppMode::Environment => self
                            .env_saved_feedback_until
                            .is_some_and(|until| now < until),
                    };
                if show_saved_badge {
                    ui.label(
                        egui::RichText::new("Saved")
                            .strong()
                            .color(egui::Color32::from_rgb(72, 175, 95)),
                    );
                } else if mode_dirty {
                    ui.label(
                        egui::RichText::new("Unsaved changes")
                            .italics()
                            .color(egui::Color32::from_rgb(255, 165, 70)),
                    );
                }
                match self.mode {
                    AppMode::Path => {
                        if path_top_bar_button(
                            ui,
                            "Changes…",
                            TopBarIcon::Changes,
                            true,
                            0.0,
                            None,
                            TopBarButtonEmphasis::Info,
                        )
                        .clicked()
                        {
                            self.change_summary_text = self.compute_change_summary();
                            self.show_change_summary = true;
                        }
                        if path_top_bar_button(
                            ui,
                            "Dedupe",
                            TopBarIcon::Dedupe,
                            true,
                            0.0,
                            None,
                            TopBarButtonEmphasis::Caution,
                        )
                        .clicked()
                        {
                            let n_drop = match self.scope {
                                Scope::Effective => path_model::adjacent_dedupe_drop_count_tagged(
                                    &self.effective_segments,
                                ),
                                _ => path_model::adjacent_dedupe_drop_count(&self.entries),
                            };
                            if n_drop == 0 {
                                self.set_status_ok(
                                    "No adjacent duplicate entries to remove.".into(),
                                );
                            } else {
                                self.show_confirm_dedupe = true;
                            }
                        }
                        if path_top_bar_button(
                            ui,
                            "Duplicates…",
                            TopBarIcon::Duplicates,
                            true,
                            0.0,
                            None,
                            TopBarButtonEmphasis::Secondary,
                        )
                        .clicked()
                        {
                            self.show_duplicate_tool = true;
                        }
                        ui.separator();
                        if path_top_bar_selectable(
                            ui,
                            matches!(
                                self.duplicate_view_filter,
                                Some(DuplicateViewFilter::OnlyDuplicates)
                            ),
                            "Only duplicates",
                            TopBarIcon::FilterDuplicates,
                        )
                        .clicked()
                        {
                            self.toggle_only_duplicates_filter();
                        }
                        if path_top_bar_selectable(
                            ui,
                            matches!(
                                self.duplicate_view_filter,
                                Some(DuplicateViewFilter::MissingPaths)
                            ),
                            "Only missing",
                            TopBarIcon::FilterMissing,
                        )
                        .clicked()
                        {
                            self.toggle_missing_path_filter();
                        }
                        ui.checkbox(&mut self.warn_missing, "Warn if folder missing");
                    }
                    AppMode::Environment => {
                        self.show_env_top_bar_extras(ui);
                    }
                }
                let skip_rm = ui
                    .checkbox(
                        &mut self.config.skip_remove_confirmation,
                        "Skip delete confirmation",
                    )
                    .on_hover_text(
                        "When checked, the X button removes a row immediately (still requires Save to write to disk). Stored in pathman.toml.",
                    );
                if skip_rm.changed() {
                    if let Err(e) = self.config.save() {
                        self.set_status_err(format!("Could not save preference: {e:#}"));
                    }
                }
                });
            });
            #[cfg(not(windows))]
            if self.mode == AppMode::Path && self.scope == Scope::User {
                ui.horizontal(|ui| {
                    if path_top_bar_button(
                        ui,
                        "Shell file…",
                        TopBarIcon::ShellFile,
                        true,
                        0.0,
                        None,
                        TopBarButtonEmphasis::None,
                    )
                    .clicked()
                    {
                        self.show_shell_settings = !self.show_shell_settings;
                    }
                    ui.label(
                        egui::RichText::new(self.config.resolved_user_shell_path().display().to_string())
                            .small(),
                    );
                });
            }
            if matches!(self.scope, Scope::System | Scope::Effective) {
                let warn = match self.mode {
                    AppMode::Path => {
                        "Changing machine (system) PATH may trigger UAC (Windows) or an admin password (macOS/Linux)."
                    }
                    AppMode::Environment => {
                        "Changing machine (system) environment variables may trigger UAC (Windows) or an admin password (macOS/Linux)."
                    }
                };
                ui.label(
                    egui::RichText::new(warn)
                        .small()
                        .color(egui::Color32::from_rgb(200, 160, 80)),
                );
            }
        });

        self.show_env_dialogs(ctx);

        let mut apply_shell_path = false;
        if self.show_shell_settings {
            egui::Window::new("User shell file")
                .open(&mut self.show_shell_settings)
                .show(ctx, |ui| {
                    ui.label("Unix user PATH is stored in a marked block inside this file (default: ~/.config/pathman/path.sh). Add one line to your shell rc: source that file, if needed.");
                    ui.horizontal(|ui| {
                        ui.label("Path:");
                        ui.add(TextEdit::singleline(&mut self.shell_path_edit).desired_width(400.0));
                    });
                    if ui.button("Apply path to config").clicked() {
                        apply_shell_path = true;
                    }
                });
        }
        if apply_shell_path {
            self.apply_config_shell_path();
        }

        let mut confirm_cancel = false;
        let mut confirm_save = false;
        if self.show_confirm_system {
            egui::Window::new(if self.scope == Scope::Effective {
                "Confirm PATH save"
            } else {
                "Confirm system PATH change"
            })
                .collapsible(false)
                .resizable(false)
                .open(&mut self.show_confirm_system)
                .show(ctx, |ui| {
                    ui.label(match self.scope {
                        Scope::Effective => "This updates user PATH and may elevate to update machine (system) PATH. A backup is written before apply. Continue?",
                        _ => "This overwrites the system PATH store for this scope. A backup is written before apply. Continue?",
                    });
                    ui.horizontal(|ui| {
                        if ui.button("Cancel").clicked() {
                            confirm_cancel = true;
                        }
                        let confirm_label = if self.scope == Scope::Effective {
                            "Save PATH"
                        } else {
                            "Save system PATH"
                        };
                        if ui.button(confirm_label).clicked() {
                            confirm_save = true;
                        }
                    });
                });
        }
        if confirm_cancel {
            self.show_confirm_system = false;
        }
        if confirm_save {
            self.show_confirm_system = false;
            self.save();
        }

        if self.show_change_summary {
            egui::Window::new("Changes vs saved PATH")
                .open(&mut self.show_change_summary)
                .default_size([560.0, 440.0])
                .show(ctx, |ui| {
                    ui.label(
                        egui::RichText::new(
                            "Entries marked − would be removed from the saved store when you save; + would be added. Order-only edits appear under “Order changed only”.",
                        )
                        .small()
                        .weak(),
                    );
                    ui.add_space(6.0);
                    ScrollArea::vertical()
                        .scroll_bar_visibility(ScrollBarVisibility::AlwaysVisible)
                        .max_height(ui.available_height().max(120.0))
                        .show(ui, |ui| {
                            ui.add(
                                egui::Label::new(
                                    egui::RichText::new(&self.change_summary_text).monospace(),
                                )
                                .wrap(),
                            );
                        });
                });
        }

        // Remove row (after X): confirm
        if let Some(i) = self.confirm_remove_index {
            let in_range = match self.scope {
                Scope::Effective => i < self.effective_segments.len(),
                Scope::User | Scope::System => i < self.entries.len(),
            };
            if !in_range {
                self.confirm_remove_index = None;
            } else {
                let preview_raw = match self.scope {
                    Scope::Effective => self.effective_segments[i].1.as_str(),
                    Scope::User | Scope::System => self.entries[i].as_str(),
                };
                let preview = truncate_path_confirm(preview_raw, 96);
                let mut window_open = true;
                let mut remove_confirmed = false;
                let mut remove_cancel = false;
                egui::Window::new("Remove PATH entry")
                    .collapsible(false)
                    .resizable(false)
                    .open(&mut window_open)
                    .show(ctx, |ui| {
                        ui.label(
                            "Remove this entry from the list? Nothing is written to disk until you click Save.",
                        );
                        ui.add_space(6.0);
                        ui.label(
                            egui::RichText::new(preview)
                                .small()
                                .monospace()
                                .color(egui::Color32::LIGHT_GRAY),
                        );
                        ui.add_space(10.0);
                        ui.horizontal(|ui| {
                            if ui.button("Cancel").clicked() {
                                remove_cancel = true;
                            }
                            if ui
                                .add(egui::Button::new("Remove").fill(egui::Color32::from_rgb(
                                    120, 42, 42,
                                )))
                                .clicked()
                            {
                                remove_confirmed = true;
                            }
                        });
                    });
                if remove_confirmed {
                    self.apply_remove_row(i);
                }
                if remove_confirmed || remove_cancel || !window_open {
                    self.confirm_remove_index = None;
                }
            }
        }

        // Dedupe: confirm
        if self.show_confirm_dedupe {
            let n_drop = match self.scope {
                Scope::Effective => {
                    path_model::adjacent_dedupe_drop_count_tagged(&self.effective_segments)
                }
                _ => path_model::adjacent_dedupe_drop_count(&self.entries),
            };
            let mut window_open = true;
            let mut run_dedupe = false;
            let mut dedupe_cancel = false;
            egui::Window::new("Dedupe PATH entries")
                .collapsible(false)
                .resizable(false)
                .open(&mut window_open)
                .show(ctx, |ui| {
                    if n_drop == 0 {
                        ui.label("No adjacent duplicate entries remain.");
                    } else {
                        ui.label(format!(
                            "Remove {n_drop} adjacent duplicate row{}? Consecutive entries with the same path will be collapsed to one row.",
                            if n_drop == 1 { "" } else { "s" }
                        ));
                        ui.label(
                            egui::RichText::new("Unsaved until you save.").small().weak(),
                        );
                    }
                    ui.add_space(10.0);
                    ui.horizontal(|ui| {
                        if ui.button("Cancel").clicked() {
                            dedupe_cancel = true;
                        }
                        if ui
                            .add_enabled(n_drop > 0, egui::Button::new("Dedupe"))
                            .clicked()
                        {
                            run_dedupe = true;
                        }
                    });
                });
            if run_dedupe && n_drop > 0 {
                if self.scope == Scope::Effective {
                    path_model::dedupe_adjacent_tagged(&mut self.effective_segments);
                } else {
                    self.entries = path_model::dedupe_adjacent(&self.entries);
                }
                self.dirty = true;
            }
            if run_dedupe || dedupe_cancel || !window_open {
                self.show_confirm_dedupe = false;
            }
        }

        if self.show_confirm_discard {
            let mut window_open = true;
            let mut discard_confirmed = false;
            let mut discard_cancel = false;
            egui::Window::new("Discard unsaved changes")
                .collapsible(false)
                .resizable(false)
                .open(&mut window_open)
                .show(ctx, |ui| {
                    ui.label(
                        "Reload from disk and drop all edits in this tab? This cannot be undone.",
                    );
                    ui.add_space(10.0);
                    ui.horizontal(|ui| {
                        if ui.button("Cancel").clicked() {
                            discard_cancel = true;
                        }
                        if ui
                            .add(egui::Button::new("Discard").fill(egui::Color32::from_rgb(
                                120, 42, 42,
                            )))
                            .clicked()
                        {
                            discard_confirmed = true;
                        }
                    });
                });
            if discard_confirmed {
                self.reload_from_store();
            }
            if discard_confirmed || discard_cancel || !window_open {
                self.show_confirm_discard = false;
            }
        }

        if self.show_duplicate_tool {
            let mut open = true;
            egui::Window::new("PATH duplicates")
                .default_width(520.0)
                .open(&mut open)
                .show(ctx, |ui| {
                    ui.label(
                        egui::RichText::new(
                            "Compares system (machine) PATH vs user PATH from disk. Switch tab or save first if you expect edits here to match.",
                        )
                        .small()
                        .weak(),
                    );
                    #[cfg(windows)]
                    ui.label(
                        egui::RichText::new("Path comparison ignores ASCII case on Windows.")
                            .small()
                            .weak(),
                    );
                    ui.add_space(6.0);
                    match self.read_stores_for_duplicate_report() {
                        Ok((m, u)) => {
                            let cross = path_model::cross_origin_duplicate_paths(&m, &u);
                            let rep_m = path_model::repeated_within_scope(&m);
                            let rep_u = path_model::repeated_within_scope(&u);
                            ui.label(
                                egui::RichText::new(format!(
                                    "System store: {} entries · User store: {} entries",
                                    m.len(),
                                    u.len()
                                ))
                                .small(),
                            );
                            ui.add_space(6.0);
                            ScrollArea::vertical()
                                .scroll_bar_visibility(ScrollBarVisibility::AlwaysVisible)
                                .max_height(380.0)
                                .auto_shrink([false, true])
                                .show(ui, |ui| {
                                    ui.label(
                                        egui::RichText::new("In both system and user PATH").strong(),
                                    );
                                    if cross.is_empty() {
                                        ui.label(
                                            egui::RichText::new(
                                                "None — no entry appears in both stores.",
                                            )
                                            .small()
                                            .weak(),
                                        );
                                    } else {
                                        ui.label(egui::RichText::new(format!(
                                            "{} path(s) appear in both stores (duplicate configuration; you can remove one side after editing).",
                                            cross.len()
                                        )).small().weak());
                                        ui.add_space(4.0);
                                        for p in &cross {
                                            ui.label(egui::RichText::new(p).small().monospace());
                                        }
                                    }
                                    ui.add_space(10.0);
                                    ui.label(
                                        egui::RichText::new("Repeated within system PATH only")
                                            .strong(),
                                    );
                                    if rep_m.is_empty() {
                                        ui.label(
                                            egui::RichText::new("None.")
                                                .small()
                                                .weak(),
                                        );
                                    } else {
                                        for (p, c) in &rep_m {
                                            ui.label(
                                                egui::RichText::new(format!("×{c}  {p}"))
                                                    .small()
                                                    .monospace(),
                                            );
                                        }
                                    }
                                    ui.add_space(10.0);
                                    ui.label(
                                        egui::RichText::new("Repeated within user PATH only")
                                            .strong(),
                                    );
                                    if rep_u.is_empty() {
                                        ui.label(
                                            egui::RichText::new("None.")
                                                .small()
                                                .weak(),
                                        );
                                    } else {
                                        for (p, c) in &rep_u {
                                            ui.label(
                                                egui::RichText::new(format!("×{c}  {p}"))
                                                    .small()
                                                    .monospace(),
                                            );
                                        }
                                    }
                                });
                        }
                        Err(e) => {
                            ui.label(
                                egui::RichText::new(format!("Could not read PATH stores: {e:#}"))
                                    .color(egui::Color32::from_rgb(255, 140, 140)),
                            );
                        }
                    }
                });
            if !open {
                self.show_duplicate_tool = false;
            }
        }

        egui::CentralPanel::default().show(ctx, |ui| {
            match self.mode {
                AppMode::Path => self.show_path_central_panel(ui),
                AppMode::Environment => self.show_env_central_panel(ui),
            }
            ui.add_space(8.0);
            if !self.status.is_empty() {
                ui.add_space(6.0);
                let color = if self.status_err {
                    egui::Color32::from_rgb(255, 120, 120)
                } else {
                    egui::Color32::LIGHT_GREEN
                };
                ui.label(egui::RichText::new(&self.status).color(color));
            }
        });
    }
}
