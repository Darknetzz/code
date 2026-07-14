use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

use eframe::egui::{self, ScrollArea, TextEdit};
use eframe::egui::scroll_area::ScrollBarVisibility;

use crate::env_model::{self, EnvEntry};
use crate::path_model::PathOrigin;
use crate::persist;
use crate::row_icons::{
    path_add_origin_menu, path_add_toolbar_button, path_row_icon_button, path_top_bar_button,
    AddToolbarIcon, PathRowIcon, TopBarButtonEmphasis, TopBarIcon,
};

use super::column_sort::{
    column_header, cmp_i32, cmp_origin, cmp_str_insensitive, EnvSortColumn, SortDir,
};
use super::helpers::{
    effective_origin_style, format_env_store_diff, origin_add_button_theme, origin_badge_label,
    truncate_path_confirm,
};
use super::{AppMode, PathmanApp, Scope};

impl PathmanApp {
    pub(crate) fn is_mode_dirty(&self) -> bool {
        match self.mode {
            AppMode::Path => self.dirty,
            AppMode::Environment => self.env_dirty,
        }
    }

    pub(crate) fn request_mode_switch(&mut self, target: AppMode) {
        if self.mode == target {
            return;
        }
        if self.is_mode_dirty() {
            self.pending_mode_switch = Some(target);
            self.show_confirm_mode_switch = true;
        } else {
            self.mode = target;
            self.reload_from_store();
        }
    }

    pub(crate) fn apply_mode_switch(&mut self, target: AppMode) {
        self.mode = target;
        self.pending_mode_switch = None;
        self.show_confirm_mode_switch = false;
        self.reload_from_store();
    }

    pub(crate) fn reload_env_from_store(&mut self) {
        self.confirm_remove_env = None;
        self.env_show_confirm_discard = false;
        self.env_saved_feedback_until = None;
        self.env_list_search.clear();
        self.env_show_change_summary = false;
        self.env_locked_names.clear();
        self.env_sort = None;
        let r = match self.scope {
            Scope::User => self.load_env_user(),
            Scope::System => self.load_env_system(),
            Scope::Effective => self.load_env_effective(),
        };
        if let Err(e) = r {
            self.set_status_err(format!("Load failed: {e:#}"));
        }
    }

    fn load_env_user(&mut self) -> anyhow::Result<()> {
        let map = persist::read_user_env(&self.config)?;
        self.env_user_baseline = map.clone();
        self.env_entries = map_to_sorted_entries(&map);
        self.env_locked_names = env_names_from_entries(&self.env_entries);
        self.env_dirty = false;
        Ok(())
    }

    fn load_env_system(&mut self) -> anyhow::Result<()> {
        let map = persist::read_system_env()?;
        self.env_system_baseline = map.clone();
        self.env_entries = map_to_sorted_entries(&map);
        self.env_locked_names = env_names_from_entries(&self.env_entries);
        self.env_dirty = false;
        Ok(())
    }

    fn load_env_effective(&mut self) -> anyhow::Result<()> {
        let m = persist::read_system_env()?;
        let u = persist::read_user_env(&self.config)?;
        self.env_user_baseline = u.clone();
        self.env_system_baseline = m.clone();
        self.env_segments = env_model::merge_machine_user_env(&m, &u);
        self.env_locked_names = env_names_from_segments(&self.env_segments);
        self.env_dirty = false;
        Ok(())
    }

    pub(crate) fn save_env(&mut self) {
        self.status_clear();
        let res = match self.scope {
            Scope::User => {
                let map = entries_to_map(&self.env_entries);
                self.save_env_user(&map)
            }
            Scope::System => {
                let map = entries_to_map(&self.env_entries);
                self.save_env_system(&map)
            }
            Scope::Effective => {
                let (machine, user) = env_model::split_origins_env(&self.env_segments);
                let skip_system = machine.is_empty() && self.env_system_baseline.is_empty();
                self.save_env_user(&user).and_then(|_| {
                    if skip_system {
                        Ok(())
                    } else {
                        self.save_env_system(&machine)
                    }
                })
            }
        };
        match res {
            Ok(()) => {
                self.env_dirty = false;
                let reload = match self.scope {
                    Scope::User => self.load_env_user(),
                    Scope::System => self.load_env_system(),
                    Scope::Effective => self.load_env_effective(),
                };
                match reload {
                    Ok(()) => {
                        self.set_status_ok(
                            "Saved. Open a new terminal for changes to apply.".into(),
                        );
                        self.env_pending_saved_feedback = true;
                    }
                    Err(e) => self.set_status_err(format!(
                        "Save succeeded but reload from disk failed: {e:#}"
                    )),
                }
            }
            Err(e) => self.set_status_err(format!("Save failed: {e:#}")),
        }
    }

    pub(crate) fn effective_env_machine_save_pending_confirm(&self) -> bool {
        let (machine, _) = env_model::split_origins_env(&self.env_segments);
        machine != self.env_system_baseline
    }

    fn save_env_user(&mut self, pending: &HashMap<String, String>) -> anyhow::Result<()> {
        let removed = env_model::diff_env(&self.env_user_baseline, pending).removed;
        #[cfg(windows)]
        {
            let prev = persist::read_user_env(&self.config).unwrap_or_default();
            let _ = persist::backup_env_json("windows-user", &prev, &backup_dir_win())?;
            persist::write_user_env(&self.config, pending, &removed)?;
        }
        #[cfg(not(windows))]
        {
            let path = self.config.resolved_user_shell_path();
            let prev = std::fs::read_to_string(&path).unwrap_or_default();
            let _ = persist::backup_string("unix-user-env", &prev)?;
            persist::write_user_env(&self.config, pending, &removed)?;
        }
        Ok(())
    }

    fn save_env_system(&mut self, pending: &HashMap<String, String>) -> anyhow::Result<()> {
        let removed = env_model::diff_env(&self.env_system_baseline, pending).removed;
        #[cfg(windows)]
        {
            let prev = persist::read_system_env().unwrap_or_default();
            let _ = persist::backup_env_json("windows-machine", &prev, &backup_dir_win())?;
            persist::request_elevated_machine_apply(persist::MachineApplyPayload {
                set: pending.clone(),
                remove: removed,
                ..Default::default()
            })?;
        }
        #[cfg(not(windows))]
        {
            let prev = read_unix_system_env_file_raw()?;
            let _ = persist::backup_string("unix-system-env", &prev)?;
            persist::write_system_env(pending, &removed)?;
        }
        Ok(())
    }

    fn read_disk_env_user(&self) -> anyhow::Result<HashMap<String, String>> {
        persist::read_user_env(&self.config)
    }

    fn read_disk_env_system(&self) -> anyhow::Result<HashMap<String, String>> {
        persist::read_system_env()
    }

    pub(crate) fn compute_env_change_summary(&self) -> String {
        let inner = || -> anyhow::Result<String> {
            let mut out = String::from(
                "Compared to what is saved on disk right now (nothing is written until you click Save):\n\n",
            );
            match self.scope {
                Scope::User => {
                    let disk = self.read_disk_env_user()?;
                    let pending = entries_to_map(&self.env_entries);
                    out.push_str(&format_env_store_diff("User environment", &disk, &pending));
                }
                Scope::System => {
                    let disk = self.read_disk_env_system()?;
                    let pending = entries_to_map(&self.env_entries);
                    out.push_str(&format_env_store_diff(
                        "Machine (system) environment",
                        &disk,
                        &pending,
                    ));
                }
                Scope::Effective => {
                    let dm = self.read_disk_env_system()?;
                    let du = self.read_disk_env_user()?;
                    let (pm, pu) = env_model::split_origins_env(&self.env_segments);
                    out.push_str(&format_env_store_diff(
                        "Machine (system) environment",
                        &dm,
                        &pm,
                    ));
                    out.push_str(&format_env_store_diff("User environment", &du, &pu));
                }
            }
            Ok(out)
        };
        match inner() {
            Ok(s) => s,
            Err(e) => format!("Could not read environment from disk to compare:\n{e:#}"),
        }
    }

    fn env_entry_matches_search(&self, name: &str, value: &str) -> bool {
        let q = self.env_list_search.trim();
        if q.is_empty() {
            return true;
        }
        let ql = q.to_lowercase();
        name.to_lowercase().contains(&ql) || value.to_lowercase().contains(&ql)
    }

    fn apply_remove_env_row(&mut self, i: usize) {
        match self.scope {
            Scope::Effective => {
                if i < self.env_segments.len() {
                    self.env_segments.remove(i);
                    self.env_dirty = true;
                }
            }
            Scope::User | Scope::System => {
                if i < self.env_entries.len() {
                    self.env_entries.remove(i);
                    self.env_dirty = true;
                }
            }
        }
    }

    fn request_remove_env_row(&mut self, i: usize) {
        if self.config.skip_remove_confirmation {
            self.apply_remove_env_row(i);
        } else {
            self.confirm_remove_env = Some(i);
        }
    }

    fn lock_env_name_at(&mut self, i: usize) {
        let name = match self.scope {
            Scope::Effective => self
                .env_segments
                .get(i)
                .map(|(_, e)| e.name.trim().to_string()),
            Scope::User | Scope::System => self
                .env_entries
                .get(i)
                .map(|e| e.name.trim().to_string()),
        };
        if let Some(name) = name {
            if !name.is_empty() && env_model::validate_var_name(&name).is_ok() {
                self.env_locked_names.insert(name);
            }
        }
    }

    fn env_name_locked(&self, name: &str) -> bool {
        let t = name.trim();
        !t.is_empty() && self.env_locked_names.contains(t)
    }

    fn toggle_env_sort(&mut self, column: EnvSortColumn) {
        let dir = match self.env_sort {
            Some((col, d)) if col == column => d.toggle(),
            _ => SortDir::Asc,
        };
        self.env_sort = Some((column, dir));
        self.apply_env_sort(column, dir);
        self.env_dirty = true;
    }

    fn apply_env_sort(&mut self, column: EnvSortColumn, dir: SortDir) {
        match self.scope {
            Scope::Effective => {
                let cross = env_model::cross_origin_env_names(
                    &self.env_system_baseline,
                    &self.env_user_baseline,
                );
                self.env_segments.sort_by(|(oa, ea), (ob, eb)| {
                    let ord = match column {
                        EnvSortColumn::Name => cmp_str_insensitive(&ea.name, &eb.name, dir),
                        EnvSortColumn::Value => cmp_str_insensitive(&ea.value, &eb.value, dir),
                        EnvSortColumn::Origin => cmp_origin(*oa, *ob, dir),
                        EnvSortColumn::Duplicate => {
                            let da = i32::from(cross.contains(&ea.name));
                            let db = i32::from(cross.contains(&eb.name));
                            cmp_i32(da, db, dir)
                        }
                    };
                    ord.then_with(|| cmp_str_insensitive(&ea.name, &eb.name, SortDir::Asc))
                });
            }
            Scope::User | Scope::System => {
                let disk_user = self.read_disk_env_user().unwrap_or_default();
                let disk_system = self.read_disk_env_system().unwrap_or_default();
                let cross = env_model::cross_origin_env_names(&disk_system, &disk_user);
                self.env_entries.sort_by(|a, b| {
                    let ord = match column {
                        EnvSortColumn::Name => cmp_str_insensitive(&a.name, &b.name, dir),
                        EnvSortColumn::Value => cmp_str_insensitive(&a.value, &b.value, dir),
                        EnvSortColumn::Origin => {
                            let row_origin = match self.scope {
                                Scope::User => PathOrigin::User,
                                Scope::System => PathOrigin::Machine,
                                Scope::Effective => unreachable!(),
                            };
                            cmp_origin(row_origin, row_origin, dir)
                        }
                        EnvSortColumn::Duplicate => {
                            let da = i32::from(!a.name.is_empty() && cross.contains(&a.name));
                            let db = i32::from(!b.name.is_empty() && cross.contains(&b.name));
                            cmp_i32(da, db, dir)
                        }
                    };
                    ord.then_with(|| cmp_str_insensitive(&a.name, &b.name, SortDir::Asc))
                });
            }
        }
    }

    fn show_env_column_headers(
        &mut self,
        ui: &mut egui::Ui,
        _scroll_w: f32,
        name_w: f32,
        value_w: f32,
        origin_w: f32,
        dup_w: f32,
    ) {
        ui.horizontal(|ui| {
            let origin_dir = self
                .env_sort
                .filter(|(c, _)| *c == EnvSortColumn::Origin)
                .map(|(_, d)| d);
            if column_header(ui, "Origin", origin_w, origin_dir).clicked() {
                self.toggle_env_sort(EnvSortColumn::Origin);
            }
            let name_dir = self
                .env_sort
                .filter(|(c, _)| *c == EnvSortColumn::Name)
                .map(|(_, d)| d);
            if column_header(ui, "Name", name_w, name_dir).clicked() {
                self.toggle_env_sort(EnvSortColumn::Name);
            }
            let value_dir = self
                .env_sort
                .filter(|(c, _)| *c == EnvSortColumn::Value)
                .map(|(_, d)| d);
            if column_header(ui, "Value", value_w, value_dir).clicked() {
                self.toggle_env_sort(EnvSortColumn::Value);
            }
            let dup_dir = self
                .env_sort
                .filter(|(c, _)| *c == EnvSortColumn::Duplicate)
                .map(|(_, d)| d);
            if column_header(ui, "Dup", dup_w, dup_dir).clicked() {
                self.toggle_env_sort(EnvSortColumn::Duplicate);
            }
            ui.add_space(26.0);
        });
        ui.add_space(2.0);
    }

    pub(crate) fn show_env_top_bar_extras(&mut self, ui: &mut egui::Ui) {
        if path_top_bar_button(
            ui,
            "Add variable",
            TopBarIcon::Changes,
            true,
            0.0,
            Some("Add a new environment variable row"),
            TopBarButtonEmphasis::Info,
        )
        .clicked()
        {
            match self.scope {
                Scope::Effective => {
                    self.env_segments.push((
                        PathOrigin::User,
                        EnvEntry {
                            name: String::new(),
                            value: String::new(),
                        },
                    ));
                }
                Scope::User | Scope::System => {
                    self.env_entries.push(EnvEntry {
                        name: String::new(),
                        value: String::new(),
                    });
                }
            }
            self.env_dirty = true;
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
            self.env_change_summary_text = self.compute_env_change_summary();
            self.env_show_change_summary = true;
        }
    }

    pub(crate) fn show_env_dialogs(&mut self, ctx: &egui::Context) {
        let mut confirm_cancel = false;
        let mut confirm_save = false;
        if self.show_confirm_env_system {
            egui::Window::new(if self.scope == Scope::Effective {
                "Confirm environment save"
            } else {
                "Confirm system environment change"
            })
            .collapsible(false)
            .resizable(false)
            .open(&mut self.show_confirm_env_system)
            .show(ctx, |ui| {
                ui.label(match self.scope {
                    Scope::Effective => "This updates user environment variables and may elevate to update machine (system) variables. A backup is written before apply. Continue?",
                    _ => "This overwrites the system environment store for this scope. A backup is written before apply. Continue?",
                });
                ui.horizontal(|ui| {
                    if ui.button("Cancel").clicked() {
                        confirm_cancel = true;
                    }
                    if ui.button("Save environment").clicked() {
                        confirm_save = true;
                    }
                });
            });
        }
        if confirm_cancel {
            self.show_confirm_env_system = false;
        }
        if confirm_save {
            self.show_confirm_env_system = false;
            self.save_env();
        }

        if self.env_show_change_summary {
            egui::Window::new("Changes vs saved environment")
                .open(&mut self.env_show_change_summary)
                .default_size([560.0, 440.0])
                .show(ctx, |ui| {
                    ScrollArea::vertical()
                        .scroll_bar_visibility(ScrollBarVisibility::AlwaysVisible)
                        .max_height(ui.available_height().max(120.0))
                        .show(ui, |ui| {
                            ui.add(
                                egui::Label::new(
                                    egui::RichText::new(&self.env_change_summary_text).monospace(),
                                )
                                .wrap(),
                            );
                        });
                });
        }

        if let Some(i) = self.confirm_remove_env {
            let in_range = match self.scope {
                Scope::Effective => i < self.env_segments.len(),
                Scope::User | Scope::System => i < self.env_entries.len(),
            };
            if !in_range {
                self.confirm_remove_env = None;
            } else {
                let preview = match self.scope {
                    Scope::Effective => self.env_segments[i].1.name.clone(),
                    Scope::User | Scope::System => self.env_entries[i].name.clone(),
                };
                let preview = truncate_path_confirm(&preview, 64);
                let mut window_open = true;
                let mut remove_confirmed = false;
                let mut remove_cancel = false;
                egui::Window::new("Remove environment variable")
                    .collapsible(false)
                    .resizable(false)
                    .open(&mut window_open)
                    .show(ctx, |ui| {
                        ui.label(
                            "Remove this variable from the list? Nothing is written to disk until you click Save.",
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
                    self.apply_remove_env_row(i);
                }
                if remove_confirmed || remove_cancel || !window_open {
                    self.confirm_remove_env = None;
                }
            }
        }

        if self.env_show_confirm_discard {
            let mut window_open = true;
            let mut discard_confirmed = false;
            let mut discard_cancel = false;
            egui::Window::new("Discard unsaved changes")
                .collapsible(false)
                .resizable(false)
                .open(&mut window_open)
                .show(ctx, |ui| {
                    ui.label(
                        "Reload from disk and drop all environment edits? This cannot be undone.",
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
                self.reload_env_from_store();
            }
            if discard_confirmed || discard_cancel || !window_open {
                self.env_show_confirm_discard = false;
            }
        }

        if self.show_confirm_mode_switch {
            let target = self.pending_mode_switch.unwrap_or(self.mode);
            let target_label = match target {
                AppMode::Path => "PATH",
                AppMode::Environment => "Environment",
            };
            let mut window_open = true;
            let mut switch_confirmed = false;
            let mut switch_cancel = false;
            egui::Window::new("Unsaved changes")
                .collapsible(false)
                .resizable(false)
                .open(&mut window_open)
                .show(ctx, |ui| {
                    ui.label(format!(
                        "You have unsaved changes in the current tab. Switch to {target_label} anyway?"
                    ));
                    ui.add_space(10.0);
                    ui.horizontal(|ui| {
                        if ui.button("Cancel").clicked() {
                            switch_cancel = true;
                        }
                        if ui
                            .add(egui::Button::new("Discard and switch").fill(egui::Color32::from_rgb(
                                120, 42, 42,
                            )))
                            .clicked()
                        {
                            switch_confirmed = true;
                        }
                    });
                });
            if switch_confirmed {
                if self.mode == AppMode::Path {
                    self.dirty = false;
                } else {
                    self.env_dirty = false;
                }
                self.apply_mode_switch(target);
            }
            if switch_confirmed || switch_cancel || !window_open {
                self.show_confirm_mode_switch = false;
                if switch_cancel {
                    self.pending_mode_switch = None;
                }
            }
        }
    }

    pub(crate) fn show_env_central_panel(&mut self, ui: &mut egui::Ui) {
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
                    "Add a user environment variable",
                    |ui| {
                        if ui.button("New variable").clicked() {
                            self.env_segments.push((
                                PathOrigin::User,
                                EnvEntry {
                                    name: String::new(),
                                    value: String::new(),
                                },
                            ));
                            self.env_dirty = true;
                            ui.close_menu();
                        }
                    },
                );
                path_add_origin_menu(
                    ui,
                    "Add machine…",
                    fill_m,
                    acc_m,
                    txt_m,
                    "Add a machine (system) environment variable",
                    |ui| {
                        if ui.button("New variable").clicked() {
                            self.env_segments.push((
                                PathOrigin::Machine,
                                EnvEntry {
                                    name: String::new(),
                                    value: String::new(),
                                },
                            ));
                            self.env_dirty = true;
                            ui.close_menu();
                        }
                    },
                );
            });
        } else {
            let row_origin = match self.scope {
                Scope::User => PathOrigin::User,
                Scope::System => PathOrigin::Machine,
                Scope::Effective => unreachable!(),
            };
            let (fill, acc, txt) = origin_add_button_theme(row_origin);
            ui.horizontal(|ui| {
                if path_add_toolbar_button(
                    ui,
                    "Add variable",
                    AddToolbarIcon::TextRow,
                    fill,
                    acc,
                    txt,
                    "Add a new environment variable",
                )
                .clicked()
                {
                    self.env_entries.push(EnvEntry {
                        name: String::new(),
                        value: String::new(),
                    });
                    self.env_dirty = true;
                }
            });
        }

        ui.horizontal(|ui| {
            ui.label("Search:");
            ui.add(
                TextEdit::singleline(&mut self.env_list_search)
                    .desired_width(280.0)
                    .hint_text("Filter by name or value…"),
            );
            if !self.env_list_search.is_empty() && ui.small_button("Clear").clicked() {
                self.env_list_search.clear();
            }
        });
        ui.label(
            egui::RichText::new("PATH is edited in the PATH tab.")
                .small()
                .weak(),
        );
        ui.add_space(4.0);

        const ORIGIN_W: f32 = 56.0;
        const BTN_W: f32 = 26.0;
        const DUP_W: f32 = 34.0;
        let scroll_w = ui.available_width();
        let gap = ui.spacing().item_spacing.x;
        let name_w = 180.0_f32;
        let row_reserve = ORIGIN_W + BTN_W + DUP_W + 3.0 * gap + name_w + 80.0;
        let value_w = (scroll_w - row_reserve).max(120.0);
        self.show_env_column_headers(ui, scroll_w, name_w, value_w, ORIGIN_W, DUP_W);

        ScrollArea::vertical()
            .id_salt("env_entries")
            .scroll_bar_visibility(ScrollBarVisibility::AlwaysVisible)
            .max_width(scroll_w)
            .auto_shrink([false, true])
            .show(ui, |ui| {
                ui.set_min_width(scroll_w);
                ui.set_max_width(scroll_w);

                let mut lock_name_at: Option<usize> = None;
                let mut remove_at: Option<usize> = None;

                if self.scope == Scope::Effective {
                    let cross = env_model::cross_origin_env_names(
                        &self.env_system_baseline,
                        &self.env_user_baseline,
                    );
                    let n = self.env_segments.len();
                    for i in 0..n {
                        let origin = self.env_segments[i].0;
                        let search_name = self.env_segments[i].1.name.clone();
                        let search_value = self.env_segments[i].1.value.clone();
                        if !self.env_entry_matches_search(&search_name, &search_value) {
                            continue;
                        }
                        let (strip_fill, origin_color) = effective_origin_style(origin);
                        let show_cross = cross.contains(&search_name);
                        let name_locked = self.env_name_locked(&search_name);
                        let row_frame = egui::Frame::none()
                            .fill(strip_fill)
                            .inner_margin(egui::Margin::symmetric(6.0, 3.0))
                            .rounding(4.0);
                        row_frame.show(ui, |ui| {
                            ui.horizontal(|ui| {
                                ui.add_sized(
                                    [ORIGIN_W, 24.0],
                                    egui::Label::new(
                                        egui::RichText::new(origin_badge_label(origin))
                                            .small()
                                            .strong()
                                            .color(origin_color),
                                    ),
                                );
                                let entry = &mut self.env_segments[i].1;
                                if name_locked {
                                    ui.add_sized(
                                        [name_w, 24.0],
                                        egui::Label::new(
                                            egui::RichText::new(&entry.name)
                                                .monospace()
                                                .strong(),
                                        ),
                                    );
                                } else {
                                    let te = ui.add_sized(
                                        [name_w, 24.0],
                                        TextEdit::singleline(&mut entry.name)
                                            .font(egui::TextStyle::Monospace)
                                            .hint_text("NAME"),
                                    );
                                    if te.lost_focus() {
                                        lock_name_at = Some(i);
                                    }
                                    if te.changed() {
                                        self.env_dirty = true;
                                    }
                                }
                                let te_val = ui.add_sized(
                                    [value_w, 24.0],
                                    TextEdit::singleline(&mut entry.value)
                                        .font(egui::TextStyle::Monospace)
                                        .hint_text("value"),
                                );
                                if te_val.changed() {
                                    self.env_dirty = true;
                                }
                                if show_cross {
                                    ui.label(egui::RichText::new("[+]").small().color(
                                        egui::Color32::from_rgb(190, 150, 255),
                                    ))
                                    .on_hover_text(
                                        "Same name exists in both user and machine stores",
                                    );
                                }
                                if path_row_icon_button(
                                    ui,
                                    [BTN_W, BTN_W],
                                    PathRowIcon::Remove,
                                    "Remove variable",
                                )
                                .clicked()
                                {
                                    remove_at = Some(i);
                                }
                            });
                        });
                    }
                } else {
                    let row_origin = match self.scope {
                        Scope::User => PathOrigin::User,
                        Scope::System => PathOrigin::Machine,
                        Scope::Effective => unreachable!(),
                    };
                    let (strip_fill, origin_color) = effective_origin_style(row_origin);
                    let disk_user = self.read_disk_env_user().unwrap_or_default();
                    let disk_system = self.read_disk_env_system().unwrap_or_default();
                    let cross = env_model::cross_origin_env_names(&disk_system, &disk_user);
                    let n = self.env_entries.len();
                    for i in 0..n {
                        let search_name = self.env_entries[i].name.clone();
                        let search_value = self.env_entries[i].value.clone();
                        if !self.env_entry_matches_search(&search_name, &search_value) {
                            continue;
                        }
                        let name_locked = self.env_name_locked(&search_name);
                        let row_frame = egui::Frame::none()
                            .fill(strip_fill)
                            .inner_margin(egui::Margin::symmetric(6.0, 3.0))
                            .rounding(4.0);
                        row_frame.show(ui, |ui| {
                            ui.horizontal(|ui| {
                                ui.add_sized(
                                    [ORIGIN_W, 24.0],
                                    egui::Label::new(
                                        egui::RichText::new(origin_badge_label(row_origin))
                                            .small()
                                            .strong()
                                            .color(origin_color),
                                    ),
                                );
                                let entry = &mut self.env_entries[i];
                                if name_locked {
                                    ui.add_sized(
                                        [name_w, 24.0],
                                        egui::Label::new(
                                            egui::RichText::new(&entry.name)
                                                .monospace()
                                                .strong(),
                                        ),
                                    );
                                } else {
                                    let te = ui.add_sized(
                                        [name_w, 24.0],
                                        TextEdit::singleline(&mut entry.name)
                                            .font(egui::TextStyle::Monospace)
                                            .hint_text("NAME"),
                                    );
                                    if te.lost_focus() {
                                        lock_name_at = Some(i);
                                    }
                                    if te.changed() {
                                        self.env_dirty = true;
                                    }
                                }
                                let te_val = ui.add_sized(
                                    [value_w, 24.0],
                                    TextEdit::singleline(&mut entry.value)
                                        .font(egui::TextStyle::Monospace)
                                        .hint_text("value"),
                                );
                                if te_val.changed() {
                                    self.env_dirty = true;
                                }
                                let show_cross =
                                    !entry.name.is_empty() && cross.contains(&entry.name);
                                if show_cross {
                                    ui.label(
                                        egui::RichText::new("[+]")
                                            .small()
                                            .color(egui::Color32::from_rgb(190, 150, 255)),
                                    );
                                }
                                if path_row_icon_button(
                                    ui,
                                    [BTN_W, BTN_W],
                                    PathRowIcon::Remove,
                                    "Remove variable",
                                )
                                .clicked()
                                {
                                    remove_at = Some(i);
                                }
                            });
                        });
                    }
                }

                if let Some(i) = lock_name_at {
                    self.lock_env_name_at(i);
                }
                if let Some(i) = remove_at {
                    self.request_remove_env_row(i);
                }
            });
    }
}

fn env_names_from_entries(entries: &[EnvEntry]) -> HashSet<String> {
    entries
        .iter()
        .map(|e| e.name.trim().to_string())
        .filter(|n| !n.is_empty())
        .collect()
}

fn env_names_from_segments(segments: &[(PathOrigin, EnvEntry)]) -> HashSet<String> {
    segments
        .iter()
        .map(|(_, e)| e.name.trim().to_string())
        .filter(|n| !n.is_empty())
        .collect()
}

fn map_to_sorted_entries(map: &HashMap<String, String>) -> Vec<EnvEntry> {
    let mut entries: Vec<EnvEntry> = map
        .iter()
        .map(|(name, value)| EnvEntry {
            name: name.clone(),
            value: value.clone(),
        })
        .collect();
    entries.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
    entries
}

fn entries_to_map(entries: &[EnvEntry]) -> HashMap<String, String> {
    let mut map = HashMap::new();
    for entry in entries {
        let name = entry.name.trim();
        if name.is_empty() || env_model::is_path_var(name) {
            continue;
        }
        if env_model::validate_var_name(name).is_ok() {
            map.insert(name.to_string(), entry.value.clone());
        }
    }
    map
}

#[cfg(windows)]
fn backup_dir_win() -> PathBuf {
    let mut d = dirs::config_dir().unwrap_or_else(|| PathBuf::from("."));
    d.push("pathman");
    d.push("backups");
    d
}

#[cfg(not(windows))]
fn read_unix_system_env_file_raw() -> anyhow::Result<String> {
    #[cfg(target_os = "macos")]
    let p = std::path::Path::new("/etc/profile.d/99-pathman-env");
    #[cfg(not(target_os = "macos"))]
    let p = std::path::Path::new("/etc/profile.d/pathman.sh");
    if p.exists() {
        Ok(std::fs::read_to_string(p)?)
    } else {
        Ok(String::new())
    }
}
