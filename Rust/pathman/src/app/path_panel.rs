use super::column_sort::{
    column_header, cmp_i32, cmp_origin, cmp_str_insensitive, path_mark_score, PathSortColumn,
    SortDir,
};
use super::helpers::*;
use super::*;
use eframe::egui::{self, ScrollArea, Sense, TextEdit};
use eframe::egui::scroll_area::ScrollBarVisibility;
use crate::path_model::{self, PathOrigin};
use crate::row_icons::{
    path_add_origin_menu, path_add_toolbar_button, path_row_icon_button, AddToolbarIcon,
    PathRowIcon,
};

impl PathmanApp {
    pub(crate) fn show_path_central_panel(&mut self, ui: &mut egui::Ui) {
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
            self.show_path_column_headers(ui, list_viewport_w);
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
                                                egui::RichText::new(format!("-> {expanded}"))
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
                                                egui::RichText::new(format!("-> {expanded}"))
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
    }

    fn toggle_path_sort(&mut self, column: PathSortColumn) {
        let dir = match self.path_sort {
            Some((col, d)) if col == column => d.toggle(),
            _ => SortDir::Asc,
        };
        self.path_sort = Some((column, dir));
        self.apply_path_sort(column, dir);
        self.dirty = true;
    }

    fn apply_path_sort(&mut self, column: PathSortColumn, dir: SortDir) {
        match self.scope {
            Scope::Effective => {
                let (cross_keys, cnt_m, cnt_u) =
                    effective_split_cross_and_counts(&self.effective_segments);
                let warn_missing = self.warn_missing;
                self.effective_segments.sort_by(|(oa, pa), (ob, pb)| {
                    let ord = match column {
                        PathSortColumn::Path => cmp_str_insensitive(pa, pb, dir),
                        PathSortColumn::Origin => cmp_origin(*oa, *ob, dir),
                        PathSortColumn::Mark => {
                            let sa = path_mark_score_for_segment(
                                pa,
                                *oa,
                                &cross_keys,
                                &cnt_m,
                                &cnt_u,
                                warn_missing,
                            );
                            let sb = path_mark_score_for_segment(
                                pb,
                                *ob,
                                &cross_keys,
                                &cnt_m,
                                &cnt_u,
                                warn_missing,
                            );
                            cmp_i32(sa, sb, dir)
                        }
                    };
                    ord.then_with(|| cmp_str_insensitive(pa, pb, SortDir::Asc))
                });
            }
            Scope::User | Scope::System => {
                let machine_for_cross = self.read_machine_slice_for_marks();
                let user_for_cross = self.read_user_slice_for_marks();
                let (cross_keys, within_counts) = tab_cross_keys_and_dup_counts(
                    self.scope,
                    &self.entries,
                    &machine_for_cross,
                    &user_for_cross,
                );
                let warn_missing = self.warn_missing;
                self.entries.sort_by(|a, b| {
                    let ord = match column {
                        PathSortColumn::Path => cmp_str_insensitive(a, b, dir),
                        PathSortColumn::Origin => {
                            let row_origin = match self.scope {
                                Scope::User => PathOrigin::User,
                                Scope::System => PathOrigin::Machine,
                                Scope::Effective => unreachable!(),
                            };
                            cmp_origin(row_origin, row_origin, dir)
                        }
                        PathSortColumn::Mark => {
                            let sa = path_mark_score_for_entry(
                                a,
                                &cross_keys,
                                &within_counts,
                                warn_missing,
                            );
                            let sb = path_mark_score_for_entry(
                                b,
                                &cross_keys,
                                &within_counts,
                                warn_missing,
                            );
                            cmp_i32(sa, sb, dir)
                        }
                    };
                    ord.then_with(|| cmp_str_insensitive(a, b, SortDir::Asc))
                });
            }
        }
    }

    fn show_path_column_headers(&mut self, ui: &mut egui::Ui, scroll_w: f32) {
        const ICON_BTN: f32 = 26.0;
        const MARK_W: f32 = 34.0;
        const ORIGIN_W: f32 = 56.0;
        let gap = ui.spacing().item_spacing.x;
        let row_reserve = MARK_W + ORIGIN_W + 5.0 * ICON_BTN + 7.0 * gap;
        let path_w = (scroll_w - row_reserve).max(48.0);

        ui.horizontal(|ui| {
            ui.add_space(3.0 * ICON_BTN + 3.0 * gap);
            let mark_dir = self
                .path_sort
                .filter(|(c, _)| *c == PathSortColumn::Mark)
                .map(|(_, d)| d);
            if column_header(ui, "Mark", MARK_W, mark_dir)
                .clicked()
            {
                self.toggle_path_sort(PathSortColumn::Mark);
            }
            let origin_dir = self
                .path_sort
                .filter(|(c, _)| *c == PathSortColumn::Origin)
                .map(|(_, d)| d);
            if column_header(ui, "Origin", ORIGIN_W, origin_dir)
                .clicked()
            {
                self.toggle_path_sort(PathSortColumn::Origin);
            }
            let path_dir = self
                .path_sort
                .filter(|(c, _)| *c == PathSortColumn::Path)
                .map(|(_, d)| d);
            if column_header(ui, "Path", path_w, path_dir).clicked() {
                self.toggle_path_sort(PathSortColumn::Path);
            }
            ui.add_space(2.0 * ICON_BTN + gap);
        });
        ui.add_space(2.0);
    }
}

fn path_mark_score_for_segment(
    path: &str,
    origin: PathOrigin,
    cross_keys: &std::collections::HashSet<String>,
    cnt_m: &std::collections::HashMap<String, usize>,
    cnt_u: &std::collections::HashMap<String, usize>,
    warn_missing: bool,
) -> i32 {
    let key = path_model::path_duplicate_key(path);
    let cross = !key.is_empty() && cross_keys.contains(&key);
    let within_n = match origin {
        PathOrigin::Machine => *cnt_m.get(&key).unwrap_or(&1),
        PathOrigin::User => *cnt_u.get(&key).unwrap_or(&1),
    };
    let warn = warn_missing && !path_model::entry_exists(path);
    path_mark_score(warn, cross, within_n)
}

fn path_mark_score_for_entry(
    path: &str,
    cross_keys: &std::collections::HashSet<String>,
    within_counts: &std::collections::HashMap<String, usize>,
    warn_missing: bool,
) -> i32 {
    let key = path_model::path_duplicate_key(path);
    let cross = !key.is_empty() && cross_keys.contains(&key);
    let within_n = *within_counts.get(&key).unwrap_or(&1);
    let warn = warn_missing && !path_model::entry_exists(path);
    path_mark_score(warn, cross, within_n)
}
