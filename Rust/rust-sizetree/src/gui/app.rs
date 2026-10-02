use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use egui::{Color32, RichText, Sense, Ui, Vec2};

use crate::gui::disk::{volume_for_path, VolumeInfo};
use crate::models::{format_count, format_size};
use crate::scan::{LiveScanHandle, ScanOptions};
use crate::tree::{NodeId, ScanPhase, ScanTree};

const POLL_INTERVAL: Duration = Duration::from_millis(100);

pub struct SizeTreeApp {
    path_edit: String,
    scan_path: PathBuf,
    include_hidden: bool,
    depth_enabled: bool,
    depth: u32,
    name_filter: String,
    kind_filter: KindFilter,
    sort_key: SortKey,
    sort_asc: bool,
    scan: Option<LiveScanHandle>,
    last_poll: Instant,
    expanded: HashSet<NodeId>,
    selected: Option<NodeId>,
    volume: Option<VolumeInfo>,
    status_note: String,
}

impl SizeTreeApp {
    pub fn new(
        cc: &eframe::CreationContext<'_>,
        path: PathBuf,
        opts: ScanOptions,
    ) -> Self {
        egui_extras::install_image_loaders(&cc.egui_ctx);
        let path_edit = path.display().to_string();
        let mut app = Self {
            path_edit,
            scan_path: path,
            include_hidden: opts.include_hidden,
            depth_enabled: opts.max_depth.is_some(),
            depth: opts.max_depth.unwrap_or(3),
            name_filter: String::new(),
            kind_filter: KindFilter::All,
            sort_key: SortKey::Size,
            sort_asc: false,
            scan: None,
            last_poll: Instant::now() - POLL_INTERVAL,
            expanded: HashSet::new(),
            selected: None,
            volume: None,
            status_note: String::new(),
        };
        app.refresh_volume();
        app.start_scan();
        app
    }

    fn current_opts(&self) -> ScanOptions {
        ScanOptions {
            max_depth: if self.depth_enabled {
                Some(self.depth)
            } else {
                None
            },
            include_hidden: self.include_hidden,
        }
    }

    fn refresh_volume(&mut self) {
        self.volume = volume_for_path(&self.scan_path);
    }

    fn start_scan(&mut self) {
        let path = PathBuf::from(self.path_edit.trim());
        let target = path.canonicalize().unwrap_or(path);
        if !target.is_dir() {
            self.status_note = format!("Not a directory: {}", target.display());
            return;
        }
        self.scan_path = target.clone();
        self.path_edit = target.display().to_string();
        let opts = self.current_opts();
        self.expanded.clear();
        self.selected = None;
        self.refresh_volume();
        self.status_note.clear();
        // Drop previous handle first (cancels + joins) before starting a new walk.
        self.scan = None;
        self.scan = Some(LiveScanHandle::start(&target, opts));
        self.last_poll = Instant::now() - POLL_INTERVAL;
    }

    fn cancel_scan(&mut self) {
        if let Some(scan) = self.scan.as_ref() {
            scan.request_cancel();
            self.status_note = "Cancelling…".into();
        }
    }

    fn with_tree<R>(&self, f: impl FnOnce(&ScanTree) -> R) -> Option<R> {
        let scan = self.scan.as_ref()?;
        let tree = scan.tree.read().ok()?;
        Some(f(&tree))
    }
}

impl eframe::App for SizeTreeApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();
        if let Some(scan) = self.scan.as_mut() {
            let _ = scan.is_finished();
        }

        if self.last_poll.elapsed() >= POLL_INTERVAL {
            self.last_poll = Instant::now();
            ctx.request_repaint_after(POLL_INTERVAL);
        } else {
            ctx.request_repaint_after(POLL_INTERVAL.saturating_sub(self.last_poll.elapsed()));
        }

        egui::Panel::top("toolbar").show(ui, |ui| {
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                ui.label("Path:");
                let response = ui.add(
                    egui::TextEdit::singleline(&mut self.path_edit)
                        .desired_width(ui.available_width() - 220.0),
                );
                if response.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter)) {
                    self.start_scan();
                }
                if ui.button("Browse…").clicked() {
                    if let Some(folder) = rfd::FileDialog::new()
                        .set_directory(&self.scan_path)
                        .pick_folder()
                    {
                        self.path_edit = folder.display().to_string();
                        self.start_scan();
                    }
                }
                if ui.button("Rescan").clicked() {
                    self.start_scan();
                }
                let scanning = self.with_tree(|t| t.phase == ScanPhase::Running).unwrap_or(false);
                if scanning && ui.button("Cancel").clicked() {
                    self.cancel_scan();
                }
            });

            ui.horizontal(|ui| {
                if ui
                    .checkbox(&mut self.include_hidden, "Show hidden")
                    .changed()
                {
                    self.start_scan();
                }
                if ui
                    .checkbox(&mut self.depth_enabled, "Max depth")
                    .changed()
                {
                    self.start_scan();
                }
                let depth_changed = ui
                    .add_enabled(
                        self.depth_enabled,
                        egui::DragValue::new(&mut self.depth).range(0..=64),
                    )
                    .changed();
                ui.label("levels");
                if depth_changed {
                    self.start_scan();
                }
                ui.separator();
                ui.label("Filter:");
                ui.add(
                    egui::TextEdit::singleline(&mut self.name_filter)
                        .desired_width(160.0)
                        .hint_text("name contains…"),
                );
                ui.label("Show:");
                egui::ComboBox::from_id_salt("kind_filter")
                    .selected_text(self.kind_filter.label())
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut self.kind_filter, KindFilter::All, "All");
                        ui.selectable_value(&mut self.kind_filter, KindFilter::Folders, "Folders");
                        ui.selectable_value(&mut self.kind_filter, KindFilter::Files, "Files");
                    });
            });
            ui.add_space(2.0);
        });

        egui::Panel::bottom("status").show(ui, |ui| {
            ui.horizontal(|ui| {
                let (phase, stats) = self
                    .with_tree(|t| (t.phase, t.stats.clone()))
                    .unwrap_or((ScanPhase::Idle, Default::default()));
                let phase_label = match phase {
                    ScanPhase::Idle => "Idle",
                    ScanPhase::Running => "Scanning…",
                    ScanPhase::Done => "Done",
                    ScanPhase::Cancelled => "Cancelled",
                };
                ui.strong(phase_label);
                ui.separator();
                ui.label(format!(
                    "{} files · {} dirs · {}",
                    format_count(stats.files),
                    format_count(stats.dirs),
                    format_size(stats.size)
                ));
                if let Some(cur) = stats.current.as_ref() {
                    ui.separator();
                    ui.colored_label(Color32::GRAY, truncate_middle(cur, 72));
                }
                if let Some(vol) = &self.volume {
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        let used = vol.used();
                        let pct = if vol.total > 0 {
                            (used as f64 / vol.total as f64) * 100.0
                        } else {
                            0.0
                        };
                        ui.label(format!(
                            "{} — used {} / {} ({pct:.0}%) · free {}",
                            vol.mount,
                            format_size(used),
                            format_size(vol.total),
                            format_size(vol.available)
                        ));
                    });
                }
            });
            if !self.status_note.is_empty() {
                ui.colored_label(Color32::from_rgb(255, 180, 80), &self.status_note);
            }
        });

        egui::Panel::right("detail")
            .default_size(320.0)
            .min_size(240.0)
            .show(ui, |ui| {
                ui.heading("Details");
                ui.separator();
                let selected = self.selected;
                let detail = self.with_tree(|tree| {
                    selected.and_then(|id| {
                        let node = tree.get(id)?;
                        let kids = tree.sorted_children(id);
                        Some((
                            node.path.clone(),
                            node.name(),
                            node.size,
                            node.file_count,
                            node.dir_count,
                            node.is_dir,
                            node.complete,
                            node.error.clone(),
                            kids.iter()
                                .filter_map(|&cid| {
                                    let c = tree.get(cid)?;
                                    Some((c.name(), c.size, c.is_dir))
                                })
                                .collect::<Vec<_>>(),
                        ))
                    })
                });

                if let Some(Some((
                    path,
                    name,
                    size,
                    files,
                    dirs,
                    is_dir,
                    complete,
                    error,
                    children,
                ))) = detail
                {
                    ui.label(RichText::new(&name).strong().size(16.0));
                    ui.label(path.display().to_string());
                    ui.add_space(6.0);
                    ui.label(format!("Size: {}", format_size(size)));
                    if is_dir {
                        ui.label(format!(
                            "Files: {} · Dirs: {}",
                            format_count(files),
                            format_count(dirs)
                        ));
                        ui.label(if complete { "Status: complete" } else { "Status: scanning…" });
                    }
                    if let Some(err) = error {
                        ui.colored_label(Color32::from_rgb(255, 100, 100), err);
                    }
                    ui.add_space(8.0);
                    ui.horizontal(|ui| {
                        if ui.button("Open in Explorer").clicked() {
                            open_in_explorer(&path);
                        }
                        if ui.button("Copy path").clicked() {
                            ui.ctx().copy_text(path.display().to_string());
                            self.status_note = "Path copied".into();
                        }
                    });
                    if is_dir && !children.is_empty() {
                        ui.add_space(10.0);
                        ui.heading("Children");
                        let max_size = children.first().map(|c| c.1).unwrap_or(1).max(1);
                        egui::ScrollArea::vertical().show(ui, |ui| {
                            for (cname, csize, cis_dir) in children.iter().take(40) {
                                let color = entry_color(*cis_dir, cname);
                                let icon = if *cis_dir { "📁" } else { "📄" };
                                ui.horizontal(|ui| {
                                    ui.label(
                                        RichText::new(format!(
                                            "{icon} {}",
                                            truncate_middle(cname, 28)
                                        ))
                                        .color(color),
                                    );
                                });
                                let frac = *csize as f32 / max_size as f32;
                                let bar = egui::ProgressBar::new(frac.clamp(0.0, 1.0))
                                    .text(format_size(*csize));
                                ui.add(bar);
                            }
                        });
                    }
                } else {
                    ui.label("Select an item in the tree.");
                }
            });

        egui::CentralPanel::default().show(ui, |ui| {
            ui.heading("Size tree");
            ui.separator();
            let snapshot = self.with_tree(|tree| {
                let root = tree.root?;
                Some(TreeSnapshot {
                    root,
                    phase: tree.phase,
                    nodes: tree
                        .nodes
                        .iter()
                        .map(|n| NodeSnap {
                            path: n.path.clone(),
                            name: n.name(),
                            size: n.size,
                            file_count: n.file_count,
                            dir_count: n.dir_count,
                            children: n.children.clone(),
                            is_dir: n.is_dir,
                            complete: n.complete,
                            error: n.error.clone(),
                        })
                        .collect(),
                })
            });

            match snapshot {
                Some(Some(snap)) => {
                    if self.expanded.is_empty() {
                        self.expanded.insert(snap.root);
                    }
                    let metrics = COL_BAR + COL_SIZE + COL_PCT + COL_FILES + COL_DIRS;
                    let gaps = ui.spacing().item_spacing.x * 5.0;
                    let name_w = (ui.available_width() - metrics - gaps - 20.0).max(180.0);
                    egui::ScrollArea::vertical()
                        .auto_shrink([false, false])
                        .show(ui, |ui| {
                            egui::Grid::new("size_tree_grid")
                                .num_columns(6)
                                .spacing([8.0, 2.0])
                                .striped(true)
                                .show(ui, |ui| {
                                    self.draw_header_row(ui, name_w);
                                    self.draw_tree_node(
                                        ui,
                                        &snap,
                                        snap.root,
                                        0,
                                        snap.nodes[snap.root].size.max(1),
                                        name_w,
                                    );
                                });
                        });
                }
                _ => {
                    ui.label("Starting scan…");
                }
            }
        });
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum SortKey {
    Name,
    Size,
    Percent,
    Files,
    Dirs,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum KindFilter {
    All,
    Folders,
    Files,
}

impl KindFilter {
    fn label(self) -> &'static str {
        match self {
            Self::All => "All",
            Self::Folders => "Folders",
            Self::Files => "Files",
        }
    }
}

struct TreeSnapshot {
    root: NodeId,
    #[allow(dead_code)]
    phase: ScanPhase,
    nodes: Vec<NodeSnap>,
}

struct NodeSnap {
    #[allow(dead_code)]
    path: PathBuf,
    name: String,
    size: u64,
    file_count: u64,
    dir_count: u64,
    children: Vec<NodeId>,
    is_dir: bool,
    complete: bool,
    error: Option<String>,
}

const COL_BAR: f32 = 120.0;
const COL_SIZE: f32 = 96.0;
const COL_PCT: f32 = 72.0;
const COL_FILES: f32 = 80.0;
const COL_DIRS: f32 = 72.0;
const ROW_H: f32 = 22.0;

impl SizeTreeApp {
    fn draw_header_row(&mut self, ui: &mut Ui, name_w: f32) {
        self.sort_header(ui, name_w, "Name", SortKey::Name, false);
        self.sort_header(ui, COL_BAR, "Share", SortKey::Percent, false);
        self.sort_header(ui, COL_SIZE, "Size", SortKey::Size, true);
        self.sort_header(ui, COL_PCT, "%", SortKey::Percent, true);
        self.sort_header(ui, COL_FILES, "Files", SortKey::Files, true);
        self.sort_header(ui, COL_DIRS, "Dirs", SortKey::Dirs, true);
        ui.end_row();
    }

    fn sort_header(&mut self, ui: &mut Ui, width: f32, title: &str, key: SortKey, right: bool) {
        let active = self.sort_key == key;
        let layout = if right {
            egui::Layout::right_to_left(egui::Align::Center)
        } else {
            egui::Layout::left_to_right(egui::Align::Center)
        };
        let response = ui
            .allocate_ui_with_layout(Vec2::new(width, ROW_H), layout, |ui| {
                let label = ui.add(
                    egui::Label::new(RichText::new(title).strong().color(Color32::GRAY))
                        .sense(Sense::click()),
                );
                let icon = if active {
                    let icon = if self.sort_asc {
                        egui_lucide::Lucide::ChevronUp
                    } else {
                        egui_lucide::Lucide::ChevronDown
                    };
                    Some(ui.add(
                        icon.size(14.0)
                            .color(Color32::GRAY)
                            .image()
                            .sense(Sense::click()),
                    ))
                } else {
                    None
                };
                label.clicked() || icon.is_some_and(|r| r.clicked())
            })
            .inner;
        if response {
            if self.sort_key == key {
                self.sort_asc = !self.sort_asc;
            } else {
                self.sort_key = key;
                self.sort_asc = matches!(key, SortKey::Name);
            }
        }
    }

    fn draw_tree_node(
        &mut self,
        ui: &mut Ui,
        snap: &TreeSnapshot,
        id: NodeId,
        depth: u32,
        parent_size: u64,
        name_w: f32,
    ) {
        let Some(node) = snap.nodes.get(id) else {
            return;
        };
        let filter = self.name_filter.trim().to_ascii_lowercase();
        if !node_visible(snap, id, &filter, self.kind_filter) {
            return;
        }

        let mut children: Vec<NodeId> = node
            .children
            .iter()
            .copied()
            .filter(|&cid| node_visible(snap, cid, &filter, self.kind_filter))
            .collect();
        sort_ids(&mut children, snap, self.sort_key, self.sort_asc);

        let has_kids = node.is_dir && !children.is_empty();
        let expanded = self.expanded.contains(&id);
        let pct = if parent_size > 0 {
            (node.size as f64 / parent_size as f64) * 100.0
        } else {
            0.0
        };
        let selected = self.selected == Some(id);
        let type_color = entry_color(node.is_dir, &node.name);

        let name_clicked = ui
            .allocate_ui_with_layout(
                Vec2::new(name_w, ROW_H),
                egui::Layout::left_to_right(egui::Align::Center),
                |ui| {
                    ui.set_min_width(name_w);
                    ui.add_space(depth as f32 * 14.0);
                    if has_kids {
                        let icon = if expanded {
                            egui_lucide::Lucide::ChevronDown
                        } else {
                            egui_lucide::Lucide::ChevronRight
                        };
                        if ui
                            .add(icon.size(16.0).color(Color32::GRAY).image().sense(Sense::click()))
                            .clicked() {
                            if expanded {
                                self.expanded.remove(&id);
                            } else {
                                self.expanded.insert(id);
                            }
                        }
                    } else {
                        ui.add_space(16.0);
                    }

                    let icon = if node.is_dir { "📁" } else { "📄" };
                    let mut label = format!("{icon} {}", node.name);
                    if !node.complete && node.is_dir {
                        label.push_str(" …");
                    }
                    if node.error.is_some() {
                        label.push_str(" ⚠");
                    }
                    let text = if selected {
                        RichText::new(label).strong().color(Color32::from_rgb(180, 210, 255))
                    } else {
                        RichText::new(label).color(type_color)
                    };
                    ui.add(egui::Label::new(text).truncate().sense(Sense::click()))
                },
            )
            .inner;
        if name_clicked.clicked() {
            self.selected = Some(id);
        }

        bar_cell(ui, pct);
        metric_cell(ui, COL_SIZE, &format_size(node.size));
        metric_cell(ui, COL_PCT, &format!("{pct:.1}%"));
        if node.is_dir {
            metric_cell(ui, COL_FILES, &format_count(node.file_count));
            metric_cell(ui, COL_DIRS, &format_count(node.dir_count));
        } else {
            metric_cell(ui, COL_FILES, "");
            metric_cell(ui, COL_DIRS, "");
        }
        ui.end_row();

        if has_kids && expanded {
            let self_size = node.size.max(1);
            for cid in children {
                self.draw_tree_node(ui, snap, cid, depth + 1, self_size, name_w);
            }
        }
    }
}

fn bar_cell(ui: &mut Ui, pct: f64) {
    ui.allocate_ui_with_layout(
        Vec2::new(COL_BAR, ROW_H),
        egui::Layout::left_to_right(egui::Align::Center),
        |ui| {
            let (bar_rect, _) = ui.allocate_exact_size(Vec2::new(COL_BAR, 12.0), Sense::hover());
            let filled = egui::Rect::from_min_size(
                bar_rect.min,
                Vec2::new(
                    bar_rect.width() * (pct as f32 / 100.0).clamp(0.0, 1.0),
                    bar_rect.height(),
                ),
            );
            ui.painter()
                .rect_filled(bar_rect, 2.0, Color32::from_rgb(40, 44, 52));
            ui.painter().rect_filled(filled, 2.0, heat_color(pct));
        },
    );
}

fn metric_cell(ui: &mut Ui, width: f32, text: &str) {
    ui.allocate_ui_with_layout(
        Vec2::new(width, ROW_H),
        egui::Layout::right_to_left(egui::Align::Center),
        |ui| {
            ui.label(
                RichText::new(text)
                    .monospace()
                    .color(Color32::from_rgb(210, 210, 210)),
            );
        },
    );
}

fn sort_ids(ids: &mut [NodeId], snap: &TreeSnapshot, key: SortKey, ascending: bool) {
    ids.sort_by(|&a, &b| {
        let na = &snap.nodes[a];
        let nb = &snap.nodes[b];
        let ord = match key {
            SortKey::Name => na.name.to_ascii_lowercase().cmp(&nb.name.to_ascii_lowercase()),
            SortKey::Size | SortKey::Percent => na.size.cmp(&nb.size),
            SortKey::Files => na.file_count.cmp(&nb.file_count),
            SortKey::Dirs => na.dir_count.cmp(&nb.dir_count),
        };
        let ord = if ascending { ord } else { ord.reverse() };
        ord.then_with(|| na.name.to_ascii_lowercase().cmp(&nb.name.to_ascii_lowercase()))
    });
}

fn node_visible(snap: &TreeSnapshot, id: NodeId, filter: &str, kind: KindFilter) -> bool {
    let Some(node) = snap.nodes.get(id) else {
        return false;
    };
    let name_ok = filter.is_empty() || node_matches_filter(snap, id, filter);
    if !name_ok {
        return false;
    }
    match kind {
        KindFilter::All => true,
        KindFilter::Folders => node.is_dir,
        KindFilter::Files => !node.is_dir || contains_file(snap, id),
    }
}

fn contains_file(snap: &TreeSnapshot, id: NodeId) -> bool {
    let Some(node) = snap.nodes.get(id) else {
        return false;
    };
    node.children.iter().any(|&cid| {
        snap.nodes
            .get(cid)
            .is_some_and(|child| !child.is_dir || contains_file(snap, cid))
    })
}

fn node_matches_filter(snap: &TreeSnapshot, id: NodeId, filter: &str) -> bool {
    let Some(node) = snap.nodes.get(id) else {
        return false;
    };
    if node.name.to_ascii_lowercase().contains(filter) {
        return true;
    }
    node.children
        .iter()
        .any(|&cid| node_matches_filter(snap, cid, filter))
}

fn entry_color(is_dir: bool, name: &str) -> Color32 {
    if is_dir {
        return Color32::from_rgb(230, 190, 90); // folders: amber
    }
    let ext = name
        .rsplit_once('.')
        .map(|(_, e)| e.to_ascii_lowercase())
        .unwrap_or_default();
    match ext.as_str() {
        // Video
        "mp4" | "mkv" | "avi" | "mov" | "wmv" | "webm" | "m4v" | "ts" | "flv" => {
            Color32::from_rgb(190, 120, 255)
        }
        // Audio
        "mp3" | "flac" | "wav" | "aac" | "ogg" | "m4a" | "wma" | "opus" => {
            Color32::from_rgb(80, 200, 220)
        }
        // Images
        "jpg" | "jpeg" | "png" | "gif" | "webp" | "bmp" | "svg" | "tiff" | "ico" => {
            Color32::from_rgb(110, 210, 130)
        }
        // Archives
        "zip" | "rar" | "7z" | "tar" | "gz" | "bz2" | "xz" | "iso" => {
            Color32::from_rgb(255, 150, 80)
        }
        // Documents
        "pdf" | "doc" | "docx" | "xls" | "xlsx" | "ppt" | "pptx" | "odt" | "rtf" => {
            Color32::from_rgb(255, 120, 120)
        }
        // Text / markup
        "txt" | "md" | "markdown" | "log" | "csv" | "json" | "xml" | "yaml" | "yml" | "toml" => {
            Color32::from_rgb(160, 200, 255)
        }
        // Code
        "rs" | "py" | "js" | "tsx" | "jsx" | "c" | "cpp" | "h" | "hpp" | "cs" | "go"
        | "java" | "kt" | "swift" | "php" | "rb" | "sh" | "ps1" | "bat" | "cmd" => {
            Color32::from_rgb(120, 220, 180)
        }
        // Executables / libs
        "exe" | "dll" | "msi" | "sys" | "bin" | "so" | "dylib" => Color32::from_rgb(255, 100, 140),
        _ => Color32::from_rgb(200, 200, 200),
    }
}

fn heat_color(pct: f64) -> Color32 {
    let t = (pct / 100.0).clamp(0.0, 1.0) as f32;
    let r = (80.0 + 175.0 * t) as u8;
    let g = (180.0 * (1.0 - t * 0.7)) as u8;
    let b = 70;
    Color32::from_rgb(r, g, b)
}

fn truncate_middle(s: &str, max: usize) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() <= max {
        return s.to_string();
    }
    let keep = max.saturating_sub(1);
    let head = keep / 2;
    let tail = keep - head;
    let mut out: String = chars.iter().take(head).collect();
    out.push('…');
    out.extend(chars.iter().rev().take(tail).rev());
    out
}

fn open_in_explorer(path: &Path) {
    #[cfg(windows)]
    {
        let _ = std::process::Command::new("explorer")
            .arg(if path.is_dir() {
                path.as_os_str().to_os_string()
            } else {
                // Select file in parent
                let mut arg = std::ffi::OsString::from("/select,");
                arg.push(path.as_os_str());
                arg
            })
            .spawn();
    }
    #[cfg(not(windows))]
    {
        let _ = open::that(path);
    }
}
