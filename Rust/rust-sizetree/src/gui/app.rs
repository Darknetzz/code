use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, Receiver, TryRecvError};
use std::time::{Duration, Instant};

use egui::{Color32, RichText, Sense, Ui, Vec2};
use egui_extras::{Column, TableBuilder};

use crate::browser::open_in_browser;
use crate::gui::disk::{volume_for_path, VolumeInfo};
use crate::gui::entry_icons::{entry_color, entry_icon};
use crate::gui::prefs::{GuiPrefs, GUI_PREFS_KEY};
use crate::models::{
    display_path, format_count, format_size, infer_report_format, strip_verbatim_prefix, DirInfo,
    ReportFormat, ScanStats,
};
use crate::report::{make_temp_report_path, slugify_for_filename, write_scan_report};
use crate::scan::{LiveScanHandle, ScanOptions};
use crate::tree::{NodeId, ScanPhase, ScanTree};

const POLL_INTERVAL: Duration = Duration::from_millis(100);

struct ReportJobOutcome {
    path: PathBuf,
    fmt: ReportFormat,
    opened: bool,
    error: Option<String>,
}

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
    /// True after we've auto-expanded the root once for the current scan.
    /// Separate from `expanded` so collapsing the root doesn't get undone next frame.
    root_seeded: bool,
    selected: Option<NodeId>,
    volume: Option<VolumeInfo>,
    status_note: String,
    prefs: GuiPrefs,
    options_open: bool,
    report_rx: Option<Receiver<ReportJobOutcome>>,
    report_busy: bool,
}

impl SizeTreeApp {
    pub fn new(
        cc: &eframe::CreationContext<'_>,
        path: PathBuf,
        opts: ScanOptions,
    ) -> Self {
        egui_extras::install_image_loaders(&cc.egui_ctx);
        let prefs = cc
            .storage
            .and_then(|s| eframe::get_value::<GuiPrefs>(s, GUI_PREFS_KEY))
            .unwrap_or_default();
        let path_edit = display_path(&path);
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
            root_seeded: false,
            selected: None,
            volume: None,
            status_note: String::new(),
            prefs,
            options_open: false,
            report_rx: None,
            report_busy: false,
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
            self.status_note = format!("Not a directory: {}", display_path(&target));
            return;
        }
        self.scan_path = target.clone();
        self.path_edit = display_path(&target);
        let opts = self.current_opts();
        self.expanded.clear();
        self.root_seeded = false;
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

    fn snapshot_dir_info(&self) -> Option<(DirInfo, PathBuf)> {
        self.with_tree(|tree| {
            tree.to_dir_info()
                .map(|info| (info, self.scan_path.clone()))
        })
        .flatten()
    }

    fn poll_report_job(&mut self) {
        let Some(rx) = self.report_rx.as_ref() else {
            return;
        };
        match rx.try_recv() {
            Ok(outcome) => {
                self.report_rx = None;
                self.report_busy = false;
                if let Some(err) = outcome.error {
                    self.status_note = format!("Report failed: {err}");
                } else if outcome.opened {
                    self.status_note = format!(
                        "Opened {} report: {}",
                        outcome.fmt.display_label(),
                        outcome.path.display()
                    );
                } else {
                    self.status_note = format!(
                        "Wrote {} report: {}",
                        outcome.fmt.display_label(),
                        outcome.path.display()
                    );
                }
            }
            Err(TryRecvError::Empty) => {}
            Err(TryRecvError::Disconnected) => {
                self.report_rx = None;
                self.report_busy = false;
                self.status_note = "Report failed: worker disconnected".into();
            }
        }
    }

    fn start_report_job(
        &mut self,
        info: DirInfo,
        target: PathBuf,
        out: PathBuf,
        fmt: ReportFormat,
        open_after: bool,
    ) {
        let limit = self.prefs.report_limit.max(1);
        let (tx, rx) = mpsc::channel();
        self.report_rx = Some(rx);
        self.report_busy = true;
        self.status_note = "Writing report…".into();
        std::thread::spawn(move || {
            let write_result = write_scan_report(&info, &target, &out, fmt, false, limit);
            let outcome = match write_result {
                Ok(()) => {
                    let opened = open_after && fmt == ReportFormat::Html && open_in_browser(&out);
                    ReportJobOutcome {
                        path: out,
                        fmt,
                        opened,
                        error: None,
                    }
                }
                Err(e) => ReportJobOutcome {
                    path: out,
                    fmt,
                    opened: false,
                    error: Some(e.to_string()),
                },
            };
            let _ = tx.send(outcome);
        });
    }

    fn report_html_open(&mut self) {
        let Some((info, target)) = self.snapshot_dir_info() else {
            self.status_note = "No scan data to export".into();
            return;
        };
        let out = make_temp_report_path(&target, ReportFormat::Html);
        self.start_report_job(info, target, out, ReportFormat::Html, true);
    }

    fn report_save_as(&mut self) {
        let Some((info, target)) = self.snapshot_dir_info() else {
            self.status_note = "No scan data to export".into();
            return;
        };
        let fmt = self.prefs.report_format;
        let ext = fmt.extension().trim_start_matches('.');
        let slug = slugify_for_filename(
            target
                .file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("root"),
        );
        let suggested = format!("rust-sizetree-{slug}{}", fmt.extension());
        let Some(mut out) = rfd::FileDialog::new()
            .set_file_name(&suggested)
            .add_filter(fmt.display_label(), &[ext])
            .add_filter("All files", &["*"])
            .save_file()
        else {
            return;
        };
        if out.extension().is_none() {
            out.set_extension(ext);
        }
        let resolved = infer_report_format(&out).unwrap_or(fmt);
        let open_after = self.prefs.open_html_after_save && resolved == ReportFormat::Html;
        self.start_report_job(info, target, out, resolved, open_after);
    }

    fn visible_columns(&self) -> Vec<TableCol> {
        let mut cols = vec![TableCol::Name];
        if self.prefs.show_share {
            cols.push(TableCol::Share);
        }
        if self.prefs.show_size {
            cols.push(TableCol::Size);
        }
        if self.prefs.show_percent {
            cols.push(TableCol::Percent);
        }
        if self.prefs.show_files {
            cols.push(TableCol::Files);
        }
        if self.prefs.show_dirs {
            cols.push(TableCol::Dirs);
        }
        cols
    }
}

impl eframe::App for SizeTreeApp {
    fn save(&mut self, storage: &mut dyn eframe::Storage) {
        eframe::set_value(storage, GUI_PREFS_KEY, &self.prefs);
    }

    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();
        if let Some(scan) = self.scan.as_mut() {
            let _ = scan.is_finished();
        }
        self.poll_report_job();

        let scanning = self
            .with_tree(|t| t.phase == ScanPhase::Running)
            .unwrap_or(false);
        if scanning {
            // Keep the indeterminate progress bar / spinner animating.
            ctx.request_repaint();
        } else if self.last_poll.elapsed() >= POLL_INTERVAL {
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
                        .desired_width(ui.available_width() - 360.0),
                );
                if response.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter)) {
                    self.start_scan();
                }
                if ui.button("Browse…").clicked() {
                    if let Some(folder) = rfd::FileDialog::new()
                        .set_directory(&self.scan_path)
                        .pick_folder()
                    {
                        self.path_edit = display_path(&folder);
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

                ui.separator();
                let can_report = !self.report_busy
                    && self
                        .with_tree(|t| t.to_dir_info().is_some())
                        .unwrap_or(false);
                ui.add_enabled_ui(can_report, |ui| {
                    ui.menu_button("Report", |ui| {
                        if ui.button("HTML (open)").clicked() {
                            ui.close();
                            self.report_html_open();
                        }
                        if ui.button("Save as…").clicked() {
                            ui.close();
                            self.report_save_as();
                        }
                    });
                });
                if ui.button("Options…").clicked() {
                    self.options_open = true;
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
                ui.separator();
                ui.checkbox(&mut self.prefs.folders_first, "Folders first")
                    .on_hover_text("Always show folders before files, regardless of sort column");
            });
            ui.add_space(2.0);
        });

        let mut options_open = self.options_open;
        egui::Window::new("Options")
            .open(&mut options_open)
            .resizable(false)
            .collapsible(false)
            .show(&ctx, |ui| {
                ui.heading("Columns");
                ui.checkbox(&mut self.prefs.show_share, "Share");
                ui.checkbox(&mut self.prefs.show_size, "Size");
                ui.checkbox(&mut self.prefs.show_percent, "%");
                ui.checkbox(&mut self.prefs.show_files, "Files");
                ui.checkbox(&mut self.prefs.show_dirs, "Dirs");
                ui.label(
                    RichText::new("Name is always visible")
                        .small()
                        .color(Color32::GRAY),
                );

                ui.add_space(10.0);
                ui.heading("Report defaults");
                egui::ComboBox::from_id_salt("report_format")
                    .selected_text(self.prefs.report_format.display_label())
                    .show_ui(ui, |ui| {
                        for fmt in [
                            ReportFormat::Html,
                            ReportFormat::Json,
                            ReportFormat::Markdown,
                            ReportFormat::Text,
                        ] {
                            ui.selectable_value(
                                &mut self.prefs.report_format,
                                fmt,
                                fmt.display_label(),
                            );
                        }
                    });
                ui.horizontal(|ui| {
                    ui.label("Child limit:");
                    ui.add(egui::DragValue::new(&mut self.prefs.report_limit).range(1..=10_000));
                });
                ui.checkbox(
                    &mut self.prefs.open_html_after_save,
                    "Open HTML after save",
                );
            });
        self.options_open = options_open;

        egui::Panel::bottom("status").show(ui, |ui| {
            ui.horizontal(|ui| {
                let (phase, stats) = self
                    .with_tree(|t| (t.phase, t.stats.clone()))
                    .unwrap_or((ScanPhase::Idle, Default::default()));
                phase_status_badge(ui, phase);
                ui.separator();
                ui.label(format!(
                    "{} files · {} dirs · {}",
                    format_count(stats.files),
                    format_count(stats.dirs),
                    format_size(stats.size)
                ));
                if let Some(cur) = stats.current.as_ref() {
                    ui.separator();
                    ui.colored_label(
                        Color32::GRAY,
                        truncate_middle(&strip_verbatim_prefix(cur), 72),
                    );
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

                let (phase, stats) = self
                    .with_tree(|t| (t.phase, t.stats.clone()))
                    .unwrap_or((ScanPhase::Idle, Default::default()));
                let scanning = phase == ScanPhase::Running;

                if scanning {
                    draw_scan_progress_panel(ui, &stats);
                    ui.add_space(10.0);
                    ui.separator();
                    ui.add_space(6.0);
                }

                let selected = self.selected;
                let folders_first = self.prefs.folders_first;
                let detail = self.with_tree(|tree| {
                    selected.and_then(|id| {
                        let node = tree.get(id)?;
                        let kids = tree.sorted_children(id);
                        let mut children: Vec<_> = kids
                            .iter()
                            .filter_map(|&cid| {
                                let c = tree.get(cid)?;
                                Some((c.name(), c.size, c.is_dir))
                            })
                            .collect();
                        if folders_first {
                            children.sort_by(|a, b| {
                                (!a.2)
                                    .cmp(&(!b.2))
                                    .then_with(|| b.1.cmp(&a.1))
                                    .then_with(|| a.0.to_ascii_lowercase().cmp(&b.0.to_ascii_lowercase()))
                            });
                        }
                        Some((
                            node.path.clone(),
                            node.name(),
                            node.size,
                            node.file_count,
                            node.dir_count,
                            node.is_dir,
                            node.complete,
                            node.error.clone(),
                            children,
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
                    ui.label(display_path(&path));
                    ui.add_space(6.0);
                    ui.label(format!("Size: {}", format_size(size)));
                    if is_dir {
                        ui.label(format!(
                            "Files: {} · Dirs: {}",
                            format_count(files),
                            format_count(dirs)
                        ));
                        ui.label(if complete {
                            "Status: complete"
                        } else {
                            "Status: scanning…"
                        });
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
                            ui.ctx().copy_text(display_path(&path));
                            self.status_note = "Path copied".into();
                        }
                    });
                    if is_dir && !children.is_empty() {
                        ui.add_space(10.0);
                        ui.heading("Children");
                        let max_size = children.iter().map(|c| c.1).max().unwrap_or(1).max(1);
                        egui::ScrollArea::vertical().show(ui, |ui| {
                            for (cname, csize, cis_dir) in children.iter().take(40) {
                                let color = entry_color(*cis_dir, cname);
                                ui.horizontal(|ui| {
                                    entry_icon(ui, *cis_dir, cname, 14.0);
                                    ui.label(
                                        RichText::new(truncate_middle(cname, 28)).color(color),
                                    );
                                });
                                let frac = *csize as f32 / max_size as f32;
                                let bar = egui::ProgressBar::new(frac.clamp(0.0, 1.0))
                                    .text(format_size(*csize));
                                ui.add(bar);
                            }
                        });
                    }
                } else if !scanning {
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
                    if !self.root_seeded {
                        self.expanded.insert(snap.root);
                        self.root_seeded = true;
                    }
                    let rows = self.collect_visible_rows(&snap);
                    let columns = self.visible_columns();
                    let mut table = TableBuilder::new(ui)
                        .striped(true)
                        .resizable(true)
                        .cell_layout(egui::Layout::left_to_right(egui::Align::Center));
                    for col in &columns {
                        table = table.column(col.builder());
                    }
                    table
                        .header(ROW_H, |mut header| {
                            self.draw_table_header(&mut header, &columns);
                        })
                        .body(|body| {
                            body.rows(ROW_H, rows.len(), |mut row| {
                                let VisibleRow {
                                    id,
                                    depth,
                                    parent_size,
                                } = rows[row.index()];
                                self.draw_table_row(
                                    &mut row,
                                    &snap,
                                    id,
                                    depth,
                                    parent_size,
                                    &columns,
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

#[derive(Clone, Copy)]
enum TableCol {
    Name,
    Share,
    Size,
    Percent,
    Files,
    Dirs,
}

impl TableCol {
    fn builder(self) -> Column {
        match self {
            Self::Name => Column::remainder().at_least(160.0).clip(true),
            Self::Share => Column::initial(COL_BAR).range(40.0..=280.0).clip(true),
            Self::Size => Column::initial(COL_SIZE).range(72.0..=200.0).clip(true),
            Self::Percent => Column::initial(COL_PCT).range(56.0..=120.0).clip(true),
            Self::Files => Column::initial(COL_FILES).range(48.0..=160.0).clip(true),
            Self::Dirs => Column::initial(COL_DIRS).range(48.0..=160.0).clip(true),
        }
    }

    fn sort_key(self) -> SortKey {
        match self {
            Self::Name => SortKey::Name,
            Self::Share | Self::Percent => SortKey::Percent,
            Self::Size => SortKey::Size,
            Self::Files => SortKey::Files,
            Self::Dirs => SortKey::Dirs,
        }
    }

    fn title(self) -> &'static str {
        match self {
            Self::Name => "Name",
            Self::Share => "Share",
            Self::Size => "Size",
            Self::Percent => "%",
            Self::Files => "Files",
            Self::Dirs => "Dirs",
        }
    }

    fn right_align_header(self) -> bool {
        matches!(
            self,
            Self::Size | Self::Percent | Self::Files | Self::Dirs
        )
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
const COL_SIZE: f32 = 108.0;
const COL_PCT: f32 = 72.0;
const COL_FILES: f32 = 80.0;
const COL_DIRS: f32 = 72.0;
const ROW_H: f32 = 22.0;

struct VisibleRow {
    id: NodeId,
    depth: u32,
    parent_size: u64,
}

impl SizeTreeApp {
    fn collect_visible_rows(&self, snap: &TreeSnapshot) -> Vec<VisibleRow> {
        let mut rows = Vec::new();
        let filter = self.name_filter.trim().to_ascii_lowercase();
        self.collect_visible_rows_rec(
            snap,
            snap.root,
            0,
            snap.nodes[snap.root].size.max(1),
            &filter,
            &mut rows,
        );
        rows
    }

    fn collect_visible_rows_rec(
        &self,
        snap: &TreeSnapshot,
        id: NodeId,
        depth: u32,
        parent_size: u64,
        filter: &str,
        out: &mut Vec<VisibleRow>,
    ) {
        if !node_visible(snap, id, filter, self.kind_filter) {
            return;
        }
        let Some(node) = snap.nodes.get(id) else {
            return;
        };
        out.push(VisibleRow {
            id,
            depth,
            parent_size,
        });

        let mut children: Vec<NodeId> = node
            .children
            .iter()
            .copied()
            .filter(|&cid| node_visible(snap, cid, filter, self.kind_filter))
            .collect();
        if node.is_dir && !children.is_empty() && self.expanded.contains(&id) {
            sort_ids(
                &mut children,
                snap,
                self.sort_key,
                self.sort_asc,
                self.prefs.folders_first,
            );
            let self_size = node.size.max(1);
            for cid in children {
                self.collect_visible_rows_rec(snap, cid, depth + 1, self_size, filter, out);
            }
        }
    }

    fn draw_table_header(
        &mut self,
        header: &mut egui_extras::TableRow<'_, '_>,
        columns: &[TableCol],
    ) {
        for col in columns {
            header.col(|ui| {
                self.sort_header_label(
                    ui,
                    col.title(),
                    col.sort_key(),
                    col.right_align_header(),
                );
            });
        }
    }

    fn sort_header_label(&mut self, ui: &mut Ui, title: &str, key: SortKey, right: bool) {
        let active = self.sort_key == key;
        let layout = if right {
            egui::Layout::right_to_left(egui::Align::Center)
        } else {
            egui::Layout::left_to_right(egui::Align::Center)
        };
        let clicked = ui
            .with_layout(layout, |ui| {
                let label = ui.add(
                    egui::Label::new(RichText::new(title).strong().color(Color32::GRAY))
                        .sense(Sense::click()),
                );
                let icon_clicked = if active {
                    let icon = if self.sort_asc {
                        egui_lucide::Lucide::ChevronUp
                    } else {
                        egui_lucide::Lucide::ChevronDown
                    };
                    ui.add(
                        icon.size(14.0)
                            .color(Color32::GRAY)
                            .image()
                            .sense(Sense::click()),
                    )
                    .clicked()
                } else {
                    false
                };
                label.clicked() || icon_clicked
            })
            .inner;
        if clicked {
            if self.sort_key == key {
                self.sort_asc = !self.sort_asc;
            } else {
                self.sort_key = key;
                self.sort_asc = matches!(key, SortKey::Name);
            }
        }
    }

    fn draw_table_row(
        &mut self,
        row: &mut egui_extras::TableRow<'_, '_>,
        snap: &TreeSnapshot,
        id: NodeId,
        depth: u32,
        parent_size: u64,
        columns: &[TableCol],
    ) {
        let Some(node) = snap.nodes.get(id) else {
            return;
        };
        let filter = self.name_filter.trim().to_ascii_lowercase();
        let children: Vec<NodeId> = node
            .children
            .iter()
            .copied()
            .filter(|&cid| node_visible(snap, cid, &filter, self.kind_filter))
            .collect();
        let has_kids = node.is_dir && !children.is_empty();
        let expanded = self.expanded.contains(&id);
        let pct = if parent_size > 0 {
            (node.size as f64 / parent_size as f64) * 100.0
        } else {
            0.0
        };
        let selected = self.selected == Some(id);
        let type_color = entry_color(node.is_dir, &node.name);

        for col in columns {
            match col {
                TableCol::Name => {
                    row.col(|ui| {
                        ui.add_space(depth as f32 * 14.0);
                        if has_kids {
                            let icon = if expanded {
                                egui_lucide::Lucide::ChevronDown
                            } else {
                                egui_lucide::Lucide::ChevronRight
                            };
                            if ui
                                .add(
                                    icon.size(16.0)
                                        .color(Color32::GRAY)
                                        .image()
                                        .sense(Sense::click()),
                                )
                                .clicked()
                            {
                                if expanded {
                                    self.expanded.remove(&id);
                                } else {
                                    self.expanded.insert(id);
                                }
                            }
                        } else {
                            ui.add_space(16.0);
                        }

                        entry_icon(ui, node.is_dir, &node.name, 16.0);
                        ui.add_space(4.0);
                        let mut label = node.name.clone();
                        if !node.complete && node.is_dir {
                            label.push_str(" …");
                        }
                        if node.error.is_some() {
                            label.push_str(" ⚠");
                        }
                        let text = if selected {
                            RichText::new(label)
                                .strong()
                                .color(Color32::from_rgb(180, 210, 255))
                        } else {
                            RichText::new(label).color(type_color)
                        };
                        if ui
                            .add(egui::Label::new(text).truncate().sense(Sense::click()))
                            .clicked()
                        {
                            self.selected = Some(id);
                        }
                    });
                }
                TableCol::Share => {
                    row.col(|ui| {
                        bar_cell(ui, pct);
                    });
                }
                TableCol::Size => {
                    row.col(|ui| {
                        metric_label(ui, &format_size(node.size));
                    });
                }
                TableCol::Percent => {
                    row.col(|ui| {
                        metric_label(ui, &format!("{pct:.1}%"));
                    });
                }
                TableCol::Files => {
                    row.col(|ui| {
                        if node.is_dir {
                            metric_label(ui, &format_count(node.file_count));
                        }
                    });
                }
                TableCol::Dirs => {
                    row.col(|ui| {
                        if node.is_dir {
                            metric_label(ui, &format_count(node.dir_count));
                        }
                    });
                }
            }
        }
    }
}

fn bar_cell(ui: &mut Ui, pct: f64) {
    let width = ui.available_width().max(8.0);
    let (bar_rect, _) = ui.allocate_exact_size(Vec2::new(width, 12.0), Sense::hover());
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
}

fn metric_label(ui: &mut Ui, text: &str) {
    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
        ui.add(
            egui::Label::new(
                RichText::new(text)
                    .monospace()
                    .color(Color32::from_rgb(210, 210, 210)),
            )
            .truncate(),
        );
    });
}

fn sort_ids(
    ids: &mut [NodeId],
    snap: &TreeSnapshot,
    key: SortKey,
    ascending: bool,
    folders_first: bool,
) {
    ids.sort_by(|&a, &b| {
        let na = &snap.nodes[a];
        let nb = &snap.nodes[b];
        if folders_first && na.is_dir != nb.is_dir {
            // Directories (is_dir=true) before files.
            return (!na.is_dir).cmp(&(!nb.is_dir));
        }
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

fn heat_color(pct: f64) -> Color32 {
    let t = (pct / 100.0).clamp(0.0, 1.0) as f32;
    let r = (80.0 + 175.0 * t) as u8;
    let g = (180.0 * (1.0 - t * 0.7)) as u8;
    let b = 70;
    Color32::from_rgb(r, g, b)
}

fn phase_status_badge(ui: &mut Ui, phase: ScanPhase) {
    let (label, fg, bg) = match phase {
        ScanPhase::Idle => (
            "Idle",
            Color32::from_rgb(210, 210, 210),
            Color32::from_rgb(70, 70, 75),
        ),
        ScanPhase::Running => (
            "Scanning…",
            Color32::from_rgb(220, 240, 255),
            Color32::from_rgb(30, 95, 170),
        ),
        ScanPhase::Done => (
            "Done",
            Color32::from_rgb(220, 255, 225),
            Color32::from_rgb(30, 120, 55),
        ),
        ScanPhase::Cancelled => (
            "Cancelled",
            Color32::from_rgb(255, 235, 210),
            Color32::from_rgb(150, 85, 25),
        ),
    };
    egui::Frame::new()
        .fill(bg)
        .corner_radius(4.0)
        .inner_margin(egui::Margin::symmetric(8, 3))
        .show(ui, |ui| {
            ui.label(RichText::new(label).color(fg).strong());
        });
}

fn draw_scan_progress_panel(ui: &mut Ui, stats: &ScanStats) {
    ui.horizontal(|ui| {
        ui.spinner();
        ui.label(
            RichText::new("Scanning…")
                .strong()
                .size(16.0)
                .color(Color32::from_rgb(120, 190, 255)),
        );
    });
    ui.add_space(6.0);

    // Indeterminate pulse — directory walks have no known total.
    let t = ui.input(|i| i.time) as f32;
    let pulse = ((t * 1.15).sin() as f32 * 0.5 + 0.5).clamp(0.05, 0.95);
    ui.add(
        egui::ProgressBar::new(pulse)
            .animate(true)
            .desired_width(ui.available_width()),
    );
    ui.add_space(8.0);

    ui.label(format!(
        "{} files · {} dirs · {}",
        format_count(stats.files),
        format_count(stats.dirs),
        format_size(stats.size)
    ));
    if let Some(cur) = stats.current.as_ref() {
        ui.add_space(4.0);
        ui.label(RichText::new("Current:").small().color(Color32::GRAY));
        ui.label(
            RichText::new(truncate_middle(&strip_verbatim_prefix(cur), 56))
                .small()
                .color(Color32::LIGHT_GRAY),
        );
    }
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
