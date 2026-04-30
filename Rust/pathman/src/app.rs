use std::path::PathBuf;

use eframe::egui;
use eframe::egui::{ScrollArea, TextEdit};

use crate::config::AppConfig;
use crate::path_model;

#[derive(Clone, Copy, PartialEq, Eq, Default)]
pub enum Scope {
    #[default]
    User,
    System,
}

pub struct PathmanApp {
    scope: Scope,
    entries: Vec<String>,
    dirty: bool,
    status: String,
    status_err: bool,
    config: AppConfig,
    show_confirm_system: bool,
    #[cfg(windows)]
    preview_merged: String,
    warn_missing: bool,
    /// Unix: show shell file path editor
    shell_path_edit: String,
    show_shell_settings: bool,
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
            dirty: false,
            status: String::new(),
            status_err: false,
            config,
            show_confirm_system: false,
            #[cfg(windows)]
            preview_merged: String::new(),
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
        };
        if let Err(e) = r {
            self.set_status_err(format!("Load failed: {e:#}"));
        }
        #[cfg(windows)]
        self.refresh_preview();
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

    #[cfg(windows)]
    fn refresh_preview(&mut self) {
        self.preview_merged = crate::persist::merged_preview().unwrap_or_default();
    }

    fn save(&mut self) {
        self.status_clear();
        let entries = path_model::dedupe_adjacent(&self.entries);
        self.entries = entries.clone();

        let res = match self.scope {
            Scope::User => self.save_user(&entries),
            Scope::System => self.save_system(&entries),
        };
        match res {
            Ok(()) => {
                self.dirty = false;
                self.set_status_ok("Saved. Open a new terminal for changes to apply.".into());
                #[cfg(windows)]
                self.refresh_preview();
            }
            Err(e) => self.set_status_err(format!("Save failed: {e:#}")),
        }
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
        if self.scope == Scope::User {
            let _ = self.load_user();
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
                ui.separator();
                if ui.button("Reload").clicked() {
                    self.reload_from_store();
                }
                if ui.button("Dedupe").clicked() {
                    self.entries = path_model::dedupe_adjacent(&self.entries);
                    self.dirty = true;
                }
                ui.checkbox(&mut self.warn_missing, "Warn if folder missing");
            });
            #[cfg(windows)]
            if self.scope == Scope::User {
                ui.label(egui::RichText::new(format!(
                    "Effective PATH preview (machine ∪ user): {}",
                    self.preview_merged
                ))
                .small());
            }
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
            if self.scope == Scope::System {
                ui.label(
                    egui::RichText::new(
                        "System scope may trigger UAC (Windows) or an admin password (macOS/Linux).",
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
            egui::Window::new("Confirm system PATH change")
                .collapsible(false)
                .resizable(false)
                .open(&mut self.show_confirm_system)
                .show(ctx, |ui| {
                    ui.label("This overwrites the system PATH store for this scope. A backup is written before apply. Continue?");
                    ui.horizontal(|ui| {
                        if ui.button("Cancel").clicked() {
                            confirm_cancel = true;
                        }
                        if ui.button("Save system PATH").clicked() {
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
            ui.horizontal(|ui| {
                if ui.button("Add folder…").clicked() {
                    if let Some(p) = rfd::FileDialog::new().pick_folder() {
                        self.entries.push(p.to_string_lossy().to_string());
                        self.dirty = true;
                    }
                }
                if ui.button("Add text row").clicked() {
                    self.entries.push(String::new());
                    self.dirty = true;
                }
            });

            ScrollArea::vertical().show(ui, |ui| {
                let mut remove_at: Option<usize> = None;
                let mut move_up: Option<usize> = None;
                let mut move_dn: Option<usize> = None;
                for (i, e) in self.entries.iter_mut().enumerate() {
                    ui.horizontal(|ui| {
                        if self.warn_missing && !path_model::entry_exists(e) {
                            ui.label(egui::RichText::new("⚠").color(egui::Color32::YELLOW));
                        } else {
                            ui.label(" ");
                        }
                        let te_resp =
                            ui.add(TextEdit::singleline(e).desired_width(520.0));
                        if te_resp.changed() {
                            self.dirty = true;
                        }
                        if ui.small_button("↑").clicked() {
                            move_up = Some(i);
                        }
                        if ui.small_button("↓").clicked() {
                            move_dn = Some(i);
                        }
                        if ui.small_button("✕").clicked() {
                            remove_at = Some(i);
                        }
                    });
                }
                if let Some(i) = remove_at {
                    if i < self.entries.len() {
                        self.entries.remove(i);
                        self.dirty = true;
                    }
                }
                if let Some(i) = move_up {
                    if i > 0 && i < self.entries.len() {
                        self.entries.swap(i, i - 1);
                        self.dirty = true;
                    }
                }
                if let Some(i) = move_dn {
                    if i + 1 < self.entries.len() {
                        self.entries.swap(i, i + 1);
                        self.dirty = true;
                    }
                }
            });

            ui.add_space(8.0);
            ui.horizontal(|ui| {
                let save_clicked = ui
                    .add_enabled(self.dirty, egui::Button::new("Save"))
                    .clicked();
                let do_save = save_clicked
                    && if self.scope == Scope::System {
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
