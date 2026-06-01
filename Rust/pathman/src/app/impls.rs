use super::*;
use super::helpers::*;

impl PathmanApp {
    pub fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        let config = AppConfig::load();
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
        };
        app.reload_from_store();
        app
    }

    fn reload_from_store(&mut self) {
        self.confirm_remove_index = None;
        self.show_confirm_dedupe = false;
        self.show_confirm_discard = false;
        self.show_duplicate_tool = false;
        self.saved_feedback_until = None;
        self.duplicate_view_filter = None;
        self.list_search.clear();
        self.show_change_summary = false;
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

    fn read_machine_slice_for_marks(&self) -> Vec<String> {
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

    fn read_user_slice_for_marks(&self) -> Vec<String> {
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
    fn row_visible_in_path_list(&self, path_str: &str, is_marked_duplicate: bool) -> bool {
        self.row_passes_duplicate_filter(path_str, is_marked_duplicate)
            && self.entry_matches_list_search(path_str)
    }

    fn toggle_path_duplicate_filter(&mut self, key: String, banner: String) {
        match &self.duplicate_view_filter {
            Some(DuplicateViewFilter::PathDuplicate { key: k, .. }) if k == &key => {
                self.duplicate_view_filter = None;
            }
            _ => {
                self.duplicate_view_filter = Some(DuplicateViewFilter::PathDuplicate { key, banner });
            }
        }
    }

    fn toggle_missing_path_filter(&mut self) {
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
    fn switch_to_effective_for_path_dup_filter(&mut self) {
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
            crate::persist::request_elevated_machine_apply(&joined)?;
        }
        #[cfg(not(windows))]
        {
            let prev = read_unix_system_file_raw()?;
            let _ = crate::persist::backup_string("unix-system", &prev);
            crate::persist::write_system_entries(entries)?;
        }
        Ok(())
    }

    fn status_clear(&mut self) {
        self.status.clear();
        self.status_err = false;
    }

    fn set_status_ok(&mut self, s: String) {
        self.status = s;
        self.status_err = false;
    }

    fn set_status_err(&mut self, s: String) {
        self.status = s;
        self.status_err = true;
    }

    /// Open the expanded path in the system file manager (Explorer, Finder, xdg-open, …).
    fn open_entry_directory(&mut self, raw_path: &str) {
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
    fn request_remove_row(&mut self, i: usize) {
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

        egui::TopBottomPanel::top("top").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("pathman");
                ui.label(egui::RichText::new("PATH editor").weak());
            });
            ui.scope(|ui| {
                let s = &mut ui.style_mut().spacing;
                // Slightly taller controls so scope tabs / buttons are not flat strips.
                let min_h = 26.0_f32;
                s.interact_size.y = s.interact_size.y.max(min_h);
                s.button_padding = egui::vec2(10.0, 6.0);
                ui.horizontal(|ui| {
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
                let save_emphasis = if self.dirty {
                    TopBarButtonEmphasis::Unsaved
                } else {
                    TopBarButtonEmphasis::IdlePrimary
                };
                let save_clicked = path_top_bar_button(
                    ui,
                    "Save",
                    TopBarIcon::Save,
                    self.dirty,
                    72.0,
                    Some("Write the current list to disk (enabled when there are unsaved changes)."),
                    save_emphasis,
                )
                .clicked();
                let needs_confirm = matches!(self.scope, Scope::System)
                    || (self.scope == Scope::Effective && self.effective_machine_save_pending_confirm());
                let do_save = save_clicked
                    && if needs_confirm {
                        self.show_confirm_system = true;
                        false
                    } else {
                        true
                    };
                if do_save {
                    self.save();
                }
                if path_top_bar_button(
                    ui,
                    "Discard",
                    TopBarIcon::Discard,
                    self.dirty,
                    0.0,
                    Some("Discard all unsaved changes and reload from disk."),
                    TopBarButtonEmphasis::Danger,
                )
                .clicked()
                {
                    self.show_confirm_discard = true;
                }
                let now = ctx.input(|i| i.time);
                let show_saved_badge = !self.dirty
                    && self
                        .saved_feedback_until
                        .is_some_and(|until| now < until);
                if show_saved_badge {
                    ui.label(
                        egui::RichText::new("Saved")
                            .strong()
                            .color(egui::Color32::from_rgb(72, 175, 95)),
                    );
                } else if self.dirty {
                    ui.label(
                        egui::RichText::new("Unsaved changes")
                            .italics()
                            .color(egui::Color32::from_rgb(255, 165, 70)),
                    );
                }
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
                        Scope::Effective => {
                            path_model::adjacent_dedupe_drop_count_tagged(&self.effective_segments)
                        }
                        _ => path_model::adjacent_dedupe_drop_count(&self.entries),
                    };
                    if n_drop == 0 {
                        self.set_status_ok("No adjacent duplicate entries to remove.".into());
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
            if self.scope == Scope::User {
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
                ui.label(
                    egui::RichText::new(
                        "Changing machine (system) PATH may trigger UAC (Windows) or an admin password (macOS/Linux).",
                    )
                    .small()
                    .color(egui::Color32::from_rgb(200, 160, 80)),
                );
            }
        });

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
            if self.scope == Scope::Effective {
                let (fill_u, acc_u, txt_u) = origin_add_button_theme(PathOrigin::User);
                let (fill_m, acc_m, txt_m) = origin_add_button_theme(PathOrigin::Machine);
                ui.horizontal(|ui| {
                    path_add_origin_menu(
                        ui,
                        "Add user…",
                        fill_u,
                        acc_u,
                        txt_u,
                        "Add to user PATH: choose Text row or Folder",
                        |ui| {
                            if ui.button("Text row").clicked() {
                                self.effective_segments
                                    .push((PathOrigin::User, String::new()));
                                self.dirty = true;
                                ui.close_menu();
                            }
                            if ui.button("Folder").clicked() {
                                ui.close_menu();
                                if let Some(p) = rfd::FileDialog::new().pick_folder() {
                                    self.effective_segments.push((
                                        PathOrigin::User,
                                        p.to_string_lossy().to_string(),
                                    ));
                                    self.dirty = true;
                                }
                            }
                        },
                    );
                    path_add_origin_menu(
                        ui,
                        "Add machine…",
                        fill_m,
                        acc_m,
                        txt_m,
                        "Add to machine PATH (before user entries): choose Text row or Folder",
                        |ui| {
                            if ui.button("Text row").clicked() {
                                let pos = self
                                    .effective_segments
                                    .iter()
                                    .position(|(o, _)| *o == PathOrigin::User)
                                    .unwrap_or(self.effective_segments.len());
                                self.effective_segments
                                    .insert(pos, (PathOrigin::Machine, String::new()));
                                self.dirty = true;
                                ui.close_menu();
                            }
                            if ui.button("Folder").clicked() {
                                ui.close_menu();
                                if let Some(p) = rfd::FileDialog::new().pick_folder() {
                                    let pos = self
                                        .effective_segments
                                        .iter()
                                        .position(|(o, _)| *o == PathOrigin::User)
                                        .unwrap_or(self.effective_segments.len());
                                    self.effective_segments.insert(
                                        pos,
                                        (PathOrigin::Machine, p.to_string_lossy().to_string()),
                                    );
                                    self.dirty = true;
                                }
                            }
                        },
                    );
                });
            } else {
                let (row_origin, hint_scope) = match self.scope {
                    Scope::User => (PathOrigin::User, "user"),
                    Scope::System => (PathOrigin::Machine, "machine (system)"),
                    Scope::Effective => unreachable!(),
                };
                let (fill, acc, txt) = origin_add_button_theme(row_origin);
                let tip_folder = format!("Pick a folder to append to {hint_scope} PATH");
                let tip_row = format!("Append an empty row to {hint_scope} PATH");
                ui.horizontal(|ui| {
                    if path_add_toolbar_button(
                        ui,
                        "Add folder…",
                        AddToolbarIcon::Folder,
                        fill,
                        acc,
                        txt,
                        &tip_folder,
                    )
                    .clicked()
                    {
                        if let Some(p) = rfd::FileDialog::new().pick_folder() {
                            self.entries.push(p.to_string_lossy().to_string());
                            self.dirty = true;
                        }
                    }
                    if path_add_toolbar_button(
                        ui,
                        "Add text row",
                        AddToolbarIcon::TextRow,
                        fill,
                        acc,
                        txt,
                        &tip_row,
                    )
                    .clicked()
                    {
                        self.entries.push(String::new());
                        self.dirty = true;
                    }
                });
            }

            ui.horizontal(|ui| {
                ui.label("Search:");
                ui.add(
                    TextEdit::singleline(&mut self.list_search)
                        .desired_width(280.0)
                        .hint_text("Filter entries…"),
                )
                .on_hover_text(
                    "Case-insensitive substring; matches the row text or expanded path (%VAR%, ~, …).",
                );
                if !self.list_search.is_empty() && ui.small_button("Clear").clicked() {
                    self.list_search.clear();
                }
            });
            ui.add_space(4.0);

            if self.duplicate_view_filter.is_some() {
                ui.horizontal(|ui| {
                    match &self.duplicate_view_filter {
                        Some(DuplicateViewFilter::PathDuplicate { banner, .. }) => {
                            ui.label(
                                egui::RichText::new(format!("Filtered — {banner}"))
                                    .small()
                                    .strong(),
                            );
                            ui.label(
                                egui::RichText::new("(same PATH entry)").small().weak(),
                            );
                        }
                        Some(DuplicateViewFilter::MissingPaths) => {
                            ui.label(
                                egui::RichText::new("Filtered — rows whose path is missing on disk")
                                    .small()
                                    .strong(),
                            );
                        }
                        Some(DuplicateViewFilter::OnlyDuplicates) => {
                            ui.label(
                                egui::RichText::new(
                                    "Filtered — duplicate entries (same path in both stores and/or repeated in one store)",
                                )
                                .small()
                                .strong(),
                            );
                        }
                        None => {}
                    }
                    if ui.small_button("Show all rows").clicked() {
                        self.duplicate_view_filter = None;
                        self.list_search.clear();
                    }
                });
                ui.add_space(4.0);
            }

            let list_viewport_w = ui.available_width();
            ScrollArea::vertical()
                .id_salt(if self.scope == Scope::Effective {
                    "path_entries_effective"
                } else {
                    "path_entries"
                })
                .scroll_bar_visibility(ScrollBarVisibility::AlwaysVisible)
                .max_width(list_viewport_w)
                .auto_shrink([false, true])
                .show(ui, |ui| {
                // Without this, scroll content width can shrink to the widest *intrinsic* child.
                // Long PATH strings would widen each row and push ^/v/X off-screen (stair-step layout).
                let scroll_w = ui.available_width();
                ui.set_min_width(scroll_w);
                ui.set_max_width(scroll_w);

                let mut move_up: Option<usize> = None;
                let mut move_dn: Option<usize> = None;
                let mut drag_reorder: Option<(usize, usize)> = None;
                // Row action icons: square hit targets (avoid wide short rects).
                const ICON_BTN: f32 = 26.0;
                const MARK_W: f32 = 34.0;
                const ORIGIN_W: f32 = 56.0;
                let btn_h = ui.spacing().interact_size.y.max(ICON_BTN);
                let gap = ui.spacing().item_spacing.x;

                if self.scope == Scope::Effective {
                    // [≡][^][v][mark][origin][text][open][X] → 8 widgets, 7 gaps.
                    let row_reserve = MARK_W + ORIGIN_W + 5.0 * ICON_BTN + 7.0 * gap;
                    let text_column_w = (scroll_w - row_reserve).max(48.0);

                    let (cross_keys_eff, cnt_m, cnt_u) =
                        effective_split_cross_and_counts(&self.effective_segments);

                    let n_seg = self.effective_segments.len();
                    for i in 0..n_seg {
                        let row_path_clone = self.effective_segments[i].1.clone();
                        let is_dup = effective_row_is_duplicate(
                            &self.effective_segments,
                            i,
                            &cross_keys_eff,
                            &cnt_m,
                            &cnt_u,
                        );
                        if !self
                            .row_visible_in_path_list(row_path_clone.as_str(), is_dup)
                        {
                            continue;
                        }

                        let warn =
                            self.warn_missing && !path_model::entry_exists(row_path_clone.as_str());
                        let prev_vis = (0..i).rev().find(|&j| {
                            let d = effective_row_is_duplicate(
                                &self.effective_segments,
                                j,
                                &cross_keys_eff,
                                &cnt_m,
                                &cnt_u,
                            );
                            self.row_visible_in_path_list(
                                self.effective_segments[j].1.as_str(),
                                d,
                            )
                        });
                        let can_up = prev_vis.map_or(false, |p| {
                            self.effective_segments[i].0 == self.effective_segments[p].0
                        });
                        let next_vis = (i + 1..n_seg).find(|&j| {
                            let d = effective_row_is_duplicate(
                                &self.effective_segments,
                                j,
                                &cross_keys_eff,
                                &cnt_m,
                                &cnt_u,
                            );
                            self.row_visible_in_path_list(
                                self.effective_segments[j].1.as_str(),
                                d,
                            )
                        });
                        let can_dn = next_vis.map_or(false, |n| {
                            self.effective_segments[i].0 == self.effective_segments[n].0
                        });

                        let origin = self.effective_segments[i].0;
                        let expanded = path_model::expanded_path(row_path_clone.as_str());
                        let key = path_model::path_duplicate_key(row_path_clone.as_str());
                        let cross = !key.is_empty() && cross_keys_eff.contains(&key);
                        let within_n = match origin {
                            PathOrigin::Machine => *cnt_m.get(&key).unwrap_or(&1),
                            PathOrigin::User => *cnt_u.get(&key).unwrap_or(&1),
                        };
                        let (mark, mark_color, mark_tip) = path_row_mark(
                            warn,
                            cross,
                            within_n,
                            PathMarkContext::Effective(origin),
                        );
                        let mark_interactive = warn || cross || within_n > 1;
                        let mark_tip = mark_tooltip_with_filter_hint(mark_tip, mark_interactive);

                        let (strip_fill, origin_color) = effective_origin_style(origin);

                        let row_frame = egui::Frame::none()
                            .fill(strip_fill)
                            .inner_margin(egui::Margin::symmetric(6.0, 3.0))
                            .rounding(4.0);
                        let row_id = ui.id().with(("eff_row_drag", i));
                        let (_row_ir, dropped_payload) =
                            ui.dnd_drop_zone::<usize, _>(row_frame, |ui| {
                                ui.vertical(|ui| {
                                    ui.horizontal(|ui| {
                                        ui.dnd_drag_source(row_id, i, |ui| {
                                            path_row_icon_button(
                                                ui,
                                                [ICON_BTN, ICON_BTN],
                                                PathRowIcon::DragHandle,
                                                "Drag to reorder",
                                            )
                                        });
                                        if ui
                                            .add_enabled_ui(can_up, |ui| {
                                                path_row_icon_button(
                                                    ui,
                                                    [ICON_BTN, ICON_BTN],
                                                    PathRowIcon::MoveUp,
                                                    if can_up {
                                                        "Move up"
                                                    } else {
                                                        "Cannot cross machine / user boundary"
                                                    },
                                                )
                                            })
                                            .inner
                                            .clicked()
                                        {
                                            move_up = Some(i);
                                        }
                                        if ui
                                            .add_enabled_ui(can_dn, |ui| {
                                                path_row_icon_button(
                                                    ui,
                                                    [ICON_BTN, ICON_BTN],
                                                    PathRowIcon::MoveDown,
                                                    if can_dn {
                                                        "Move down"
                                                    } else {
                                                        "Cannot cross machine / user boundary"
                                                    },
                                                )
                                            })
                                            .inner
                                            .clicked()
                                        {
                                            move_dn = Some(i);
                                        }

                                        let mut mark_resp = ui.add_sized(
                                            [MARK_W, btn_h],
                                            egui::Label::new(
                                                egui::RichText::new(&mark)
                                                    .small()
                                                    .monospace()
                                                    .color(mark_color),
                                            )
                                            .sense(if mark_interactive {
                                                Sense::click()
                                            } else {
                                                Sense::hover()
                                            }),
                                        );
                                        if let Some(t) = mark_tip {
                                            mark_resp = mark_resp.on_hover_text(t);
                                        }
                                        if mark_resp.clicked() && mark_interactive {
                                            if warn {
                                                self.toggle_missing_path_filter();
                                            } else if !key.is_empty() && (cross || within_n > 1) {
                                                let ban =
                                                    truncate_path_confirm(row_path_clone.as_str(), 56);
                                                self.toggle_path_duplicate_filter(key, ban);
                                            }
                                        }

                                        ui.add_sized(
                                            [ORIGIN_W, btn_h],
                                            egui::Label::new(
                                                egui::RichText::new(origin_badge_label(origin))
                                                    .small()
                                                    .strong()
                                                    .color(origin_color),
                                            ),
                                        );

                                        let e = &mut self.effective_segments[i].1;
                                        let te_resp = ui.add_sized(
                                            egui::vec2(text_column_w, btn_h),
                                            TextEdit::singleline(e)
                                                .desired_width(text_column_w)
                                                .clip_text(true)
                                                .font(egui::TextStyle::Monospace)
                                                .id_salt(("eff", i)),
                                        );
                                        if te_resp.changed() {
                                            self.dirty = true;
                                        }

                                        let can_open = !path_model::expanded_path(
                                            self.effective_segments[i].1.as_str(),
                                        )
                                        .trim()
                                        .is_empty();
                                        if ui
                                            .add_enabled_ui(can_open, |ui| {
                                                path_row_icon_button(
                                                    ui,
                                                    [ICON_BTN, ICON_BTN],
                                                    PathRowIcon::OpenDirectory,
                                                    "Open in file manager",
                                                )
                                            })
                                            .inner
                                            .clicked()
                                        {
                                            let p = self.effective_segments[i].1.clone();
                                            self.open_entry_directory(&p);
                                        }
                                        if path_row_icon_button(
                                            ui,
                                            [ICON_BTN, ICON_BTN],
                                            PathRowIcon::Remove,
                                            "Remove row",
                                        )
                                        .clicked()
                                        {
                                            self.request_remove_row(i);
                                        }
                                    });

                                    let row_text = self.effective_segments[i].1.clone();
                                    if expanded != row_text {
                                        ui.horizontal(|ui| {
                                            ui.add_space(
                                                3.0 * ICON_BTN + 3.0 * gap + MARK_W + gap + ORIGIN_W + gap,
                                            );
                                            ui.label(
                                                egui::RichText::new(format!("→ {expanded}"))
                                                    .small()
                                                    .color(origin_color.gamma_multiply(0.75))
                                                    .monospace(),
                                            );
                                        });
                                    }
                                });
                            });
                        if let Some(from) = dropped_payload {
                            let from = *from;
                            if from != i {
                                drag_reorder = Some((from, i));
                            }
                        }
                    }
                } else {
                    // [≡][^][v][mark][Machine|User][text][open][X] — align with Effective scope layout.
                    const ORIGIN_W: f32 = 56.0;
                    let row_reserve = MARK_W + ORIGIN_W + 5.0 * ICON_BTN + 7.0 * gap;
                    let text_column_w = (scroll_w - row_reserve).max(48.0);

                    let row_origin = match self.scope {
                        Scope::User => PathOrigin::User,
                        Scope::System => PathOrigin::Machine,
                        Scope::Effective => unreachable!(),
                    };
                    let (strip_fill, origin_color) = effective_origin_style(row_origin);

                    let machine_for_cross = self.read_machine_slice_for_marks();
                    let user_for_cross = self.read_user_slice_for_marks();
                    let (cross_keys_tab, within_counts_tab) = tab_cross_keys_and_dup_counts(
                        self.scope,
                        &self.entries,
                        &machine_for_cross,
                        &user_for_cross,
                    );
                    let mark_ctx_tab = match self.scope {
                        Scope::User => PathMarkContext::SingleUser,
                        Scope::System => PathMarkContext::SingleSystem,
                        Scope::Effective => unreachable!(),
                    };

                    let n_entries = self.entries.len();
                    for i in 0..n_entries {
                        let is_dup = tab_row_is_duplicate(
                            &self.entries,
                            i,
                            &cross_keys_tab,
                            &within_counts_tab,
                        );
                        if !self.row_visible_in_path_list(self.entries[i].as_str(), is_dup) {
                            continue;
                        }

                        let prev_vis = (0..i).rev().find(|&j| {
                            let d = tab_row_is_duplicate(
                                &self.entries,
                                j,
                                &cross_keys_tab,
                                &within_counts_tab,
                            );
                            self.row_visible_in_path_list(self.entries[j].as_str(), d)
                        });
                        let can_up = prev_vis.is_some();
                        let next_vis = (i + 1..n_entries).find(|&j| {
                            let d = tab_row_is_duplicate(
                                &self.entries,
                                j,
                                &cross_keys_tab,
                                &within_counts_tab,
                            );
                            self.row_visible_in_path_list(self.entries[j].as_str(), d)
                        });
                        let can_dn = next_vis.is_some();

                        let expanded = path_model::expanded_path(self.entries[i].as_str());
                        let warn =
                            self.warn_missing && !path_model::entry_exists(self.entries[i].as_str());
                        let key = path_model::path_duplicate_key(self.entries[i].as_str());
                        let cross = !key.is_empty() && cross_keys_tab.contains(&key);
                        let within_n = *within_counts_tab.get(&key).unwrap_or(&1);
                        let (mark, mark_color, mark_tip) =
                            path_row_mark(warn, cross, within_n, mark_ctx_tab);
                        let mark_interactive = warn || cross || within_n > 1;
                        let mark_tip =
                            mark_tooltip_with_filter_hint(mark_tip, mark_interactive);

                        let row_frame = egui::Frame::none()
                            .fill(strip_fill)
                            .inner_margin(egui::Margin::symmetric(6.0, 3.0))
                            .rounding(4.0);
                        let row_id = ui.id().with(("scope_row_drag", i));
                        let (_row_ir, dropped_payload) =
                            ui.dnd_drop_zone::<usize, _>(row_frame, |ui| {
                                ui.vertical(|ui| {
                                    ui.horizontal(|ui| {
                                        ui.dnd_drag_source(row_id, i, |ui| {
                                            path_row_icon_button(
                                                ui,
                                                [ICON_BTN, ICON_BTN],
                                                PathRowIcon::DragHandle,
                                                "Drag to reorder",
                                            )
                                        });
                                        if ui
                                            .add_enabled_ui(can_up, |ui| {
                                                path_row_icon_button(
                                                    ui,
                                                    [ICON_BTN, ICON_BTN],
                                                    PathRowIcon::MoveUp,
                                                    "Move up",
                                                )
                                            })
                                            .inner
                                            .clicked()
                                        {
                                            move_up = Some(i);
                                        }
                                        if ui
                                            .add_enabled_ui(can_dn, |ui| {
                                                path_row_icon_button(
                                                    ui,
                                                    [ICON_BTN, ICON_BTN],
                                                    PathRowIcon::MoveDown,
                                                    "Move down",
                                                )
                                            })
                                            .inner
                                            .clicked()
                                        {
                                            move_dn = Some(i);
                                        }

                                        let mut mark_resp = ui.add_sized(
                                            [MARK_W, btn_h],
                                            egui::Label::new(
                                                egui::RichText::new(&mark)
                                                    .small()
                                                    .monospace()
                                                    .color(mark_color),
                                            )
                                            .sense(if mark_interactive {
                                                Sense::click()
                                            } else {
                                                Sense::hover()
                                            }),
                                        );
                                        if let Some(t) = mark_tip {
                                            mark_resp = mark_resp.on_hover_text(t);
                                        }
                                        if mark_resp.clicked() && mark_interactive {
                                            if warn {
                                                self.toggle_missing_path_filter();
                                            } else if !key.is_empty() && (cross || within_n > 1) {
                                                let ban =
                                                    truncate_path_confirm(self.entries[i].as_str(), 56);
                                                self.toggle_path_duplicate_filter(key, ban);
                                                self.switch_to_effective_for_path_dup_filter();
                                            }
                                        }

                                        ui.add_sized(
                                            [ORIGIN_W, btn_h],
                                            egui::Label::new(
                                                egui::RichText::new(origin_badge_label(row_origin))
                                                    .small()
                                                    .strong()
                                                    .color(origin_color),
                                            ),
                                        );

                                        let te_resp = ui.add_sized(
                                            egui::vec2(text_column_w, btn_h),
                                            TextEdit::singleline(&mut self.entries[i])
                                                .desired_width(text_column_w)
                                                .clip_text(true)
                                                .font(egui::TextStyle::Monospace)
                                                .id_salt(i),
                                        );
                                        if te_resp.changed() {
                                            self.dirty = true;
                                        }

                                        let can_open = !path_model::expanded_path(self.entries[i].as_str())
                                            .trim()
                                            .is_empty();
                                        if ui
                                            .add_enabled_ui(can_open, |ui| {
                                                path_row_icon_button(
                                                    ui,
                                                    [ICON_BTN, ICON_BTN],
                                                    PathRowIcon::OpenDirectory,
                                                    "Open in file manager",
                                                )
                                            })
                                            .inner
                                            .clicked()
                                        {
                                            let p = self.entries[i].clone();
                                            self.open_entry_directory(&p);
                                        }
                                        if path_row_icon_button(
                                            ui,
                                            [ICON_BTN, ICON_BTN],
                                            PathRowIcon::Remove,
                                            "Remove row",
                                        )
                                        .clicked()
                                        {
                                            self.request_remove_row(i);
                                        }
                                    });

                                    if expanded != self.entries[i] {
                                        ui.horizontal(|ui| {
                                            ui.add_space(
                                                3.0 * ICON_BTN + 3.0 * gap + MARK_W + gap + ORIGIN_W + gap,
                                            );
                                            ui.label(
                                                egui::RichText::new(format!("→ {expanded}"))
                                                    .small()
                                                    .color(origin_color.gamma_multiply(0.75))
                                                    .monospace(),
                                            );
                                        });
                                    }
                                });
                            });
                        if let Some(from) = dropped_payload {
                            let from = *from;
                            if from != i {
                                drag_reorder = Some((from, i));
                            }
                        }
                    }
                }

                if let Some((from, to)) = drag_reorder {
                    if self.scope == Scope::Effective {
                        let n = self.effective_segments.len();
                        if from < n && to < n && self.effective_segments[from].0 == self.effective_segments[to].0
                        {
                            let row = self.effective_segments.remove(from);
                            let insert_at = if from < to { to - 1 } else { to };
                            self.effective_segments.insert(insert_at, row);
                            self.dirty = true;
                        }
                    } else {
                        let n = self.entries.len();
                        if from < n && to < n {
                            let row = self.entries.remove(from);
                            let insert_at = if from < to { to - 1 } else { to };
                            self.entries.insert(insert_at, row);
                            self.dirty = true;
                        }
                    }
                }

                if let Some(i) = move_up {
                    if self.scope == Scope::Effective {
                        let n = self.effective_segments.len();
                        if i < n {
                            let (cross_keys_eff, cnt_m, cnt_u) =
                                effective_split_cross_and_counts(&self.effective_segments);
                            let prev = (0..i).rev().find(|&j| {
                                let d = effective_row_is_duplicate(
                                    &self.effective_segments,
                                    j,
                                    &cross_keys_eff,
                                    &cnt_m,
                                    &cnt_u,
                                );
                                self.row_visible_in_path_list(
                                    self.effective_segments[j].1.as_str(),
                                    d,
                                )
                            });
                            if let Some(p) = prev {
                                if self.effective_segments[i].0 == self.effective_segments[p].0 {
                                    self.effective_segments.swap(i, p);
                                    self.dirty = true;
                                }
                            }
                        }
                    } else if i < self.entries.len() {
                        let machine_for_cross = self.read_machine_slice_for_marks();
                        let user_for_cross = self.read_user_slice_for_marks();
                        let (cross_keys_tab, within_counts_tab) = tab_cross_keys_and_dup_counts(
                            self.scope,
                            &self.entries,
                            &machine_for_cross,
                            &user_for_cross,
                        );
                        let prev = (0..i).rev().find(|&j| {
                            let d = tab_row_is_duplicate(
                                &self.entries,
                                j,
                                &cross_keys_tab,
                                &within_counts_tab,
                            );
                            self.row_visible_in_path_list(self.entries[j].as_str(), d)
                        });
                        if let Some(p) = prev {
                            self.entries.swap(i, p);
                            self.dirty = true;
                        }
                    }
                }
                if let Some(i) = move_dn {
                    if self.scope == Scope::Effective {
                        let n = self.effective_segments.len();
                        if i < n {
                            let (cross_keys_eff, cnt_m, cnt_u) =
                                effective_split_cross_and_counts(&self.effective_segments);
                            let next = (i + 1..n).find(|&j| {
                                let d = effective_row_is_duplicate(
                                    &self.effective_segments,
                                    j,
                                    &cross_keys_eff,
                                    &cnt_m,
                                    &cnt_u,
                                );
                                self.row_visible_in_path_list(
                                    self.effective_segments[j].1.as_str(),
                                    d,
                                )
                            });
                            if let Some(ni) = next {
                                if self.effective_segments[i].0 == self.effective_segments[ni].0 {
                                    self.effective_segments.swap(i, ni);
                                    self.dirty = true;
                                }
                            }
                        }
                    } else {
                        let n = self.entries.len();
                        if i < n {
                            let machine_for_cross = self.read_machine_slice_for_marks();
                            let user_for_cross = self.read_user_slice_for_marks();
                            let (cross_keys_tab, within_counts_tab) = tab_cross_keys_and_dup_counts(
                                self.scope,
                                &self.entries,
                                &machine_for_cross,
                                &user_for_cross,
                            );
                            let next = (i + 1..n).find(|&j| {
                                let d = tab_row_is_duplicate(
                                    &self.entries,
                                    j,
                                    &cross_keys_tab,
                                    &within_counts_tab,
                                );
                                self.row_visible_in_path_list(self.entries[j].as_str(), d)
                            });
                            if let Some(ni) = next {
                                self.entries.swap(i, ni);
                                self.dirty = true;
                            }
                        }
                    }
                }
            });

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
