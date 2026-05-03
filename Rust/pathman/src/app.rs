use std::path::PathBuf;

use eframe::egui;
use eframe::egui::{ScrollArea, TextEdit};

use crate::config::AppConfig;
use crate::path_model::{self, PathOrigin};
use crate::row_icons::{
    mix_srgb, path_add_toolbar_button, path_row_icon_button, AddToolbarIcon, PathRowIcon,
};

#[derive(Clone, Copy, PartialEq, Eq, Default)]
pub enum Scope {
    #[default]
    User,
    System,
    /// Merged machine + user view (editable).
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
    warn_missing: bool,
    /// Unix: show shell file path editor
    shell_path_edit: String,
    show_shell_settings: bool,
}

fn origin_badge_label(origin: PathOrigin) -> &'static str {
    match origin {
        PathOrigin::Machine => "Machine",
        PathOrigin::User => "User",
    }
}

/// Row strip fill and accent color for path rows (Effective merged view; User tab = user tint; System tab = machine tint).
fn effective_origin_style(origin: PathOrigin) -> (egui::Color32, egui::Color32) {
    match origin {
        PathOrigin::Machine => (
            egui::Color32::from_rgb(26, 34, 52),
            egui::Color32::from_rgb(130, 185, 255),
        ),
        PathOrigin::User => (
            egui::Color32::from_rgb(34, 42, 30),
            egui::Color32::from_rgb(165, 215, 145),
        ),
    }
}

/// Fill, accent, and label colors for “add to user / machine” toolbar buttons (matches row strip hues).
fn origin_add_button_theme(origin: PathOrigin) -> (egui::Color32, egui::Color32, egui::Color32) {
    let (strip_fill, accent) = effective_origin_style(origin);
    let fill = mix_srgb(strip_fill, accent, 0.14);
    let text = egui::Color32::from_rgb(248, 248, 252);
    (fill, accent, text)
}

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
            warn_missing: true,
            shell_path_edit,
            show_shell_settings: false,
        };
        app.reload_from_store();
        app
    }

    fn reload_from_store(&mut self) {
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
            let m = crate::persist::read_system_entries(&self.config)?;
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
                self.save_user(&user).and_then(|_| self.save_system(&machine))
            }
        };
        match res {
            Ok(()) => {
                self.dirty = false;
                self.set_status_ok("Saved. Open a new terminal for changes to apply.".into());
                if self.scope == Scope::Effective {
                    let _ = self.load_effective();
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
        let joined = path_model::join(entries);
        #[cfg(windows)]
        {
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
        let joined = path_model::join(entries);
        #[cfg(windows)]
        {
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
                if ui
                    .selectable_label(self.scope == Scope::User, "User")
                    .clicked()
                {
                    self.scope = Scope::User;
                    self.reload_from_store();
                }
                if ui
                    .selectable_label(self.scope == Scope::System, "System")
                    .clicked()
                {
                    self.scope = Scope::System;
                    self.reload_from_store();
                }
                if ui
                    .selectable_label(self.scope == Scope::Effective, "Effective")
                    .clicked()
                {
                    self.scope = Scope::Effective;
                    self.reload_from_store();
                }
                ui.separator();
                if ui.button("Reload").clicked() {
                    self.reload_from_store();
                }
                if ui.button("Dedupe").clicked() {
                    if self.scope == Scope::Effective {
                        path_model::dedupe_adjacent_tagged(&mut self.effective_segments);
                    } else {
                        self.entries = path_model::dedupe_adjacent(&self.entries);
                    }
                    self.dirty = true;
                }
                ui.checkbox(&mut self.warn_missing, "Warn if folder missing");
                });
            });
            #[cfg(not(windows))]
            if self.scope == Scope::User {
                ui.horizontal(|ui| {
                    if ui.button("Shell file…").clicked() {
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

        egui::CentralPanel::default().show(ctx, |ui| {
            if self.scope == Scope::Effective {
                let (fill_u, acc_u, txt_u) = origin_add_button_theme(PathOrigin::User);
                let (fill_m, acc_m, txt_m) = origin_add_button_theme(PathOrigin::Machine);
                ui.horizontal(|ui| {
                    if path_add_toolbar_button(
                        ui,
                        "Add folder… (user)",
                        AddToolbarIcon::Folder,
                        fill_u,
                        acc_u,
                        txt_u,
                        "Pick a folder to append to user PATH",
                    )
                    .clicked()
                    {
                        if let Some(p) = rfd::FileDialog::new().pick_folder() {
                            self.effective_segments.push((
                                PathOrigin::User,
                                p.to_string_lossy().to_string(),
                            ));
                            self.dirty = true;
                        }
                    }
                    if path_add_toolbar_button(
                        ui,
                        "Add folder… (machine)",
                        AddToolbarIcon::Folder,
                        fill_m,
                        acc_m,
                        txt_m,
                        "Pick a folder to insert into machine PATH (before user entries)",
                    )
                    .clicked()
                    {
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
                    if path_add_toolbar_button(
                        ui,
                        "Add text row (user)",
                        AddToolbarIcon::TextRow,
                        fill_u,
                        acc_u,
                        txt_u,
                        "Append an empty row to user PATH",
                    )
                    .clicked()
                    {
                        self.effective_segments
                            .push((PathOrigin::User, String::new()));
                        self.dirty = true;
                    }
                    if path_add_toolbar_button(
                        ui,
                        "Add text row (machine)",
                        AddToolbarIcon::TextRow,
                        fill_m,
                        acc_m,
                        txt_m,
                        "Insert an empty machine PATH row (before user entries)",
                    )
                    .clicked()
                    {
                        let pos = self
                            .effective_segments
                            .iter()
                            .position(|(o, _)| *o == PathOrigin::User)
                            .unwrap_or(self.effective_segments.len());
                        self.effective_segments
                            .insert(pos, (PathOrigin::Machine, String::new()));
                        self.dirty = true;
                    }
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

            let list_viewport_w = ui.available_width();
            ScrollArea::vertical()
                .id_salt(if self.scope == Scope::Effective {
                    "path_entries_effective"
                } else {
                    "path_entries"
                })
                .max_width(list_viewport_w)
                .auto_shrink([false, true])
                .show(ui, |ui| {
                // Without this, scroll content width can shrink to the widest *intrinsic* child.
                // Long PATH strings would widen each row and push ^/v/X off-screen (stair-step layout).
                let scroll_w = ui.available_width();
                ui.set_min_width(scroll_w);
                ui.set_max_width(scroll_w);

                let mut remove_at: Option<usize> = None;
                let mut move_up: Option<usize> = None;
                let mut move_dn: Option<usize> = None;
                // Row action icons: square hit targets (avoid wide short rects).
                const ICON_BTN: f32 = 26.0;
                const MARK_W: f32 = 28.0;
                const ORIGIN_W: f32 = 56.0;
                let btn_h = ui.spacing().interact_size.y.max(ICON_BTN);
                let gap = ui.spacing().item_spacing.x;

                if self.scope == Scope::Effective {
                    // [mark][origin][text][^][v][X] → 6 widgets, 5 gaps.
                    let row_reserve = MARK_W + ORIGIN_W + 3.0 * ICON_BTN + 5.0 * gap;
                    let text_column_w = (scroll_w - row_reserve).max(48.0);

                    let n_seg = self.effective_segments.len();
                    for i in 0..n_seg {
                        let can_up = i > 0
                            && self.effective_segments[i].0 == self.effective_segments[i - 1].0;
                        let can_dn = i + 1 < n_seg
                            && self.effective_segments[i].0 == self.effective_segments[i + 1].0;
                        let origin = self.effective_segments[i].0;
                        let expanded = path_model::expanded_path(self.effective_segments[i].1.as_str());
                        let warn = self.warn_missing
                            && !path_model::entry_exists(self.effective_segments[i].1.as_str());
                        let mark = if warn { "[!]" } else { "   " };
                        let mark_color = if warn {
                            egui::Color32::from_rgb(220, 180, 60)
                        } else {
                            egui::Color32::TRANSPARENT
                        };

                        let (strip_fill, origin_color) = effective_origin_style(origin);

                        egui::Frame::none()
                            .fill(strip_fill)
                            .inner_margin(egui::Margin::symmetric(6.0, 3.0))
                            .rounding(4.0)
                            .show(ui, |ui| {
                                ui.vertical(|ui| {
                                    ui.horizontal(|ui| {
                                        let mark_resp = ui.add_sized(
                                            [MARK_W, btn_h],
                                            egui::Label::new(
                                                egui::RichText::new(mark)
                                                    .small()
                                                    .monospace()
                                                    .color(mark_color),
                                            ),
                                        );
                                        if warn {
                                            mark_resp.on_hover_text(
                                                "Path not found or not a directory (after expanding env vars)",
                                            );
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
                                        if path_row_icon_button(
                                            ui,
                                            [ICON_BTN, ICON_BTN],
                                            PathRowIcon::Remove,
                                            "Remove row",
                                        )
                                        .clicked()
                                        {
                                            remove_at = Some(i);
                                        }
                                    });

                                    let row_text = self.effective_segments[i].1.clone();
                                    if expanded != row_text {
                                        ui.horizontal(|ui| {
                                            ui.add_space(MARK_W + gap + ORIGIN_W + gap);
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
                    }
                } else {
                    // [mark][Machine|User][text][^][v][X] — align with Effective scope layout.
                    const ORIGIN_W: f32 = 56.0;
                    let row_reserve = MARK_W + ORIGIN_W + 3.0 * ICON_BTN + 5.0 * gap;
                    let text_column_w = (scroll_w - row_reserve).max(48.0);

                    let row_origin = match self.scope {
                        Scope::User => PathOrigin::User,
                        Scope::System => PathOrigin::Machine,
                        Scope::Effective => unreachable!(),
                    };
                    let (strip_fill, origin_color) = effective_origin_style(row_origin);

                    for (i, e) in self.entries.iter_mut().enumerate() {
                        let expanded = path_model::expanded_path(e.as_str());
                        let warn = self.warn_missing && !path_model::entry_exists(e.as_str());
                        let mark = if warn { "[!]" } else { "   " };
                        let mark_color = if warn {
                            egui::Color32::from_rgb(220, 180, 60)
                        } else {
                            egui::Color32::TRANSPARENT
                        };

                        egui::Frame::none()
                            .fill(strip_fill)
                            .inner_margin(egui::Margin::symmetric(6.0, 3.0))
                            .rounding(4.0)
                            .show(ui, |ui| {
                                ui.vertical(|ui| {
                                    ui.horizontal(|ui| {
                                        let mark_resp = ui.add_sized(
                                            [MARK_W, btn_h],
                                            egui::Label::new(
                                                egui::RichText::new(mark)
                                                    .small()
                                                    .monospace()
                                                    .color(mark_color),
                                            ),
                                        );
                                        if warn {
                                            mark_resp.on_hover_text(
                                                "Path not found or not a directory (after expanding env vars)",
                                            );
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
                                            TextEdit::singleline(e)
                                                .desired_width(text_column_w)
                                                .clip_text(true)
                                                .font(egui::TextStyle::Monospace)
                                                .id_salt(i),
                                        );
                                        if te_resp.changed() {
                                            self.dirty = true;
                                        }

                                        if path_row_icon_button(
                                            ui,
                                            [ICON_BTN, ICON_BTN],
                                            PathRowIcon::MoveUp,
                                            "Move up",
                                        )
                                        .clicked()
                                        {
                                            move_up = Some(i);
                                        }
                                        if path_row_icon_button(
                                            ui,
                                            [ICON_BTN, ICON_BTN],
                                            PathRowIcon::MoveDown,
                                            "Move down",
                                        )
                                        .clicked()
                                        {
                                            move_dn = Some(i);
                                        }
                                        if path_row_icon_button(
                                            ui,
                                            [ICON_BTN, ICON_BTN],
                                            PathRowIcon::Remove,
                                            "Remove row",
                                        )
                                        .clicked()
                                        {
                                            remove_at = Some(i);
                                        }
                                    });

                                    if expanded != *e {
                                        ui.horizontal(|ui| {
                                            ui.add_space(MARK_W + gap + ORIGIN_W + gap);
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
                    }
                }

                if let Some(i) = remove_at {
                    if self.scope == Scope::Effective {
                        if i < self.effective_segments.len() {
                            self.effective_segments.remove(i);
                            self.dirty = true;
                        }
                    } else if i < self.entries.len() {
                        self.entries.remove(i);
                        self.dirty = true;
                    }
                }
                if let Some(i) = move_up {
                    if self.scope == Scope::Effective {
                        if i > 0
                            && i < self.effective_segments.len()
                            && self.effective_segments[i].0 == self.effective_segments[i - 1].0
                        {
                            self.effective_segments.swap(i, i - 1);
                            self.dirty = true;
                        }
                    } else if i > 0 && i < self.entries.len() {
                        self.entries.swap(i, i - 1);
                        self.dirty = true;
                    }
                }
                if let Some(i) = move_dn {
                    if self.scope == Scope::Effective {
                        if i + 1 < self.effective_segments.len()
                            && self.effective_segments[i].0 == self.effective_segments[i + 1].0
                        {
                            self.effective_segments.swap(i, i + 1);
                            self.dirty = true;
                        }
                    } else if i + 1 < self.entries.len() {
                        self.entries.swap(i, i + 1);
                        self.dirty = true;
                    }
                }
            });

            ui.add_space(8.0);
            ui.horizontal(|ui| {
                let save_clicked = ui
                    .add_enabled(
                        self.dirty,
                        egui::Button::new("Save").min_size(egui::vec2(72.0, 28.0)),
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
                if self.dirty {
                    ui.label(egui::RichText::new("Unsaved changes").italics());
                }
            });

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
