use std::fs;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock};
use std::thread::{self, JoinHandle};

use anyhow::Result;

use crate::models::{DirSummary, ScanStats};
use crate::progress::ScanProgress;
use crate::tree::{NodeId, ScanPhase, ScanTree};

#[derive(Clone, Copy, Debug, Default)]
pub struct ScanOptions {
    pub max_depth: Option<u32>,
    pub include_hidden: bool,
}

/// Synchronous scan for CLI `scan` / `report`. Builds a live arena internally and
/// returns the finished [`crate::models::DirInfo`].
pub fn scan_directory_with(
    path: &Path,
    opts: &ScanOptions,
    _current_depth: u32,
    progress: Option<&mut ScanProgress>,
) -> Result<crate::models::DirInfo> {
    let tree = Arc::new(RwLock::new(ScanTree::new()));
    let cancel = Arc::new(AtomicBool::new(false));
    {
        let mut t = tree.write().expect("scan tree lock");
        t.phase = ScanPhase::Running;
    }
    walk_root(path, opts, &tree, &cancel, progress);
    let mut t = tree.write().expect("scan tree lock");
    if cancel.load(Ordering::Relaxed) {
        t.phase = ScanPhase::Cancelled;
    } else {
        t.phase = ScanPhase::Done;
    }
    t.to_dir_info()
        .ok_or_else(|| anyhow::anyhow!("scan produced no root"))
}

/// Shared handle for a background live scan (GUI).
pub struct LiveScanHandle {
    pub tree: Arc<RwLock<ScanTree>>,
    cancel: Arc<AtomicBool>,
    join: Option<JoinHandle<()>>,
}

impl LiveScanHandle {
    pub fn start(path: &Path, opts: ScanOptions) -> Self {
        let tree = Arc::new(RwLock::new(ScanTree::new()));
        let cancel = Arc::new(AtomicBool::new(false));
        {
            let mut t = tree.write().expect("scan tree lock");
            t.clear();
            t.phase = ScanPhase::Running;
        }
        let tree_bg = Arc::clone(&tree);
        let cancel_bg = Arc::clone(&cancel);
        let path = path.to_path_buf();
        let join = thread::spawn(move || {
            walk_root(&path, &opts, &tree_bg, &cancel_bg, None);
            let mut t = tree_bg.write().expect("scan tree lock");
            if cancel_bg.load(Ordering::Relaxed) {
                t.phase = ScanPhase::Cancelled;
            } else {
                t.phase = ScanPhase::Done;
            }
        });
        Self {
            tree,
            cancel,
            join: Some(join),
        }
    }

    pub fn request_cancel(&self) {
        self.cancel.store(true, Ordering::Relaxed);
    }

    pub fn is_finished(&mut self) -> bool {
        if let Some(handle) = self.join.as_ref() {
            if handle.is_finished() {
                if let Some(h) = self.join.take() {
                    let _ = h.join();
                }
                return true;
            }
            return false;
        }
        true
    }
}

impl Drop for LiveScanHandle {
    fn drop(&mut self) {
        self.cancel.store(true, Ordering::Relaxed);
        if let Some(handle) = self.join.take() {
            let _ = handle.join();
        }
    }
}

fn walk_root(
    path: &Path,
    opts: &ScanOptions,
    tree: &Arc<RwLock<ScanTree>>,
    cancel: &AtomicBool,
    mut progress: Option<&mut ScanProgress>,
) {
    let root_id = {
        let mut t = tree.write().expect("scan tree lock");
        t.insert_dir(path, None)
    };
    walk_dir(path, root_id, 0, opts, tree, cancel, &mut progress);
}

fn walk_dir(
    path: &Path,
    id: NodeId,
    current_depth: u32,
    opts: &ScanOptions,
    tree: &Arc<RwLock<ScanTree>>,
    cancel: &AtomicBool,
    progress: &mut Option<&mut ScanProgress>,
) {
    {
        let mut t = tree.write().expect("scan tree lock");
        t.stats.current = Some(path.display().to_string());
        notify_progress(progress, &t.stats);
    }

    if cancel.load(Ordering::Relaxed) {
        let mut t = tree.write().expect("scan tree lock");
        t.mark_complete(id);
        return;
    }

    let entries = match fs::read_dir(path) {
        Ok(it) => it.filter_map(Result::ok).collect::<Vec<_>>(),
        Err(e) if e.kind() == std::io::ErrorKind::PermissionDenied => {
            let mut t = tree.write().expect("scan tree lock");
            t.set_error(id, "Permission denied".to_string());
            t.mark_complete(id);
            return;
        }
        Err(e) => {
            let mut t = tree.write().expect("scan tree lock");
            t.set_error(id, e.to_string());
            t.mark_complete(id);
            return;
        }
    };

    for entry in entries {
        if cancel.load(Ordering::Relaxed) {
            break;
        }

        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        if !opts.include_hidden && entry_is_hidden(&entry, &name_str) {
            continue;
        }

        let item = entry.path();
        let ft = match entry.file_type() {
            Ok(ft) => ft,
            Err(_) => continue,
        };
        if ft.is_symlink() {
            continue;
        }

        if ft.is_file() {
            if let Ok(meta) = entry.metadata() {
                let sz = meta.len();
                let mut t = tree.write().expect("scan tree lock");
                t.insert_file(&item, id, sz);
                t.stats.current = Some(item.display().to_string());
                notify_progress(progress, &t.stats);
            }
        } else if ft.is_dir() {
            let expand = opts
                .max_depth
                .map(|max| current_depth < max)
                .unwrap_or(true);

            if expand {
                let child_id = {
                    let mut t = tree.write().expect("scan tree lock");
                    t.insert_dir(&item, Some(id))
                };
                walk_dir(
                    &item,
                    child_id,
                    current_depth + 1,
                    opts,
                    tree,
                    cancel,
                    progress,
                );
            } else {
                let child_id = {
                    let mut t = tree.write().expect("scan tree lock");
                    t.insert_dir(&item, Some(id))
                };
                // Release the tree lock while walking the leaf so the GUI can poll.
                let mut stats_scratch = {
                    let t = tree.read().expect("scan tree lock");
                    t.stats.clone()
                };
                let summary = get_dir_size(&item, &mut stats_scratch, progress);
                let mut t = tree.write().expect("scan tree lock");
                t.stats = stats_scratch;
                t.set_leaf_totals(
                    child_id,
                    summary.size,
                    summary.files,
                    summary.dirs,
                    summary.error,
                );
                notify_progress(progress, &t.stats);
            }
        }
    }

    let mut t = tree.write().expect("scan tree lock");
    t.sort_children(id);
    t.mark_complete(id);
    t.stats.current = Some(path.display().to_string());
    notify_progress(progress, &t.stats);
}

fn entry_is_hidden(entry: &fs::DirEntry, name: &str) -> bool {
    if name.starts_with('.') {
        return true;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if let Ok(meta) = entry.metadata() {
            const FILE_ATTRIBUTE_HIDDEN: u32 = 0x2;
            if meta.file_attributes() & FILE_ATTRIBUTE_HIDDEN != 0 {
                return true;
            }
        }
    }
    false
}

pub fn get_dir_size(
    path: &Path,
    stats: &mut ScanStats,
    progress: &mut Option<&mut ScanProgress>,
) -> DirSummary {
    let mut summary = DirSummary {
        size: 0,
        files: 0,
        dirs: 0,
        error: None,
    };
    walk_dir_size(path, &mut summary, stats, progress);
    summary
}

fn walk_dir_size(
    path: &Path,
    summary: &mut DirSummary,
    stats: &mut ScanStats,
    progress: &mut Option<&mut ScanProgress>,
) {
    stats.current = Some(path.display().to_string());
    notify_progress(progress, stats);

    let entries = match fs::read_dir(path) {
        Ok(it) => it,
        Err(e) => {
            summary.error = Some(e.to_string());
            return;
        }
    };
    for entry in entries.flatten() {
        let ft = match entry.file_type() {
            Ok(ft) => ft,
            Err(_) => continue,
        };
        if ft.is_symlink() {
            continue;
        }
        if ft.is_dir() {
            summary.dirs += 1;
            stats.dirs += 1;
            walk_dir_size(&entry.path(), summary, stats, progress);
        } else if ft.is_file() {
            if let Ok(meta) = entry.metadata() {
                let sz = meta.len();
                summary.size += sz;
                summary.files += 1;
                stats.files += 1;
                stats.size += sz;
                notify_progress(progress, stats);
            }
        }
    }
}

fn notify_progress(progress: &mut Option<&mut ScanProgress>, stats: &ScanStats) {
    if let Some(p) = progress.as_deref_mut() {
        p.notify(stats);
    }
}
