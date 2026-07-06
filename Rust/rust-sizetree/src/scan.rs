use std::fs;
use std::path::Path;

use anyhow::Result;

use crate::models::{DirInfo, DirSummary, ScanStats};
use crate::progress::ScanProgress;

#[derive(Clone, Copy, Debug, Default)]
pub struct ScanOptions {
    pub max_depth: Option<u32>,
    pub include_hidden: bool,
}

pub fn scan_directory(
    path: &Path,
    max_depth: Option<u32>,
    current_depth: u32,
) -> Result<DirInfo> {
    scan_directory_with(
        path,
        &ScanOptions {
            max_depth,
            include_hidden: false,
        },
        current_depth,
        None,
    )
}

pub fn scan_directory_with(
    path: &Path,
    opts: &ScanOptions,
    current_depth: u32,
    progress: Option<&mut ScanProgress>,
) -> Result<DirInfo> {
    let mut progress = progress;
    let mut stats = ScanStats::default();
    Ok(scan_directory_inner(
        path,
        opts,
        current_depth,
        &mut stats,
        &mut progress,
    ))
}

fn scan_directory_inner(
    path: &Path,
    opts: &ScanOptions,
    current_depth: u32,
    stats: &mut ScanStats,
    progress: &mut Option<&mut ScanProgress>,
) -> DirInfo {
    stats.current = Some(path.display().to_string());
    notify_progress(progress, stats);

    let mut total_size = 0u64;
    let mut file_count = 0u64;
    let mut dir_count = 0u64;
    let mut children = Vec::new();
    let mut error = None;

    let entries = match fs::read_dir(path) {
        Ok(it) => it.filter_map(Result::ok).collect::<Vec<_>>(),
        Err(e) if e.kind() == std::io::ErrorKind::PermissionDenied => {
            error = Some("Permission denied".to_string());
            Vec::new()
        }
        Err(e) => {
            error = Some(e.to_string());
            Vec::new()
        }
    };

    for entry in entries {
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
            match entry.metadata() {
                Ok(meta) => {
                    let sz = meta.len();
                    total_size += sz;
                    file_count += 1;
                    stats.files += 1;
                    stats.size += sz;
                    notify_progress(progress, stats);
                    children.push(DirInfo {
                        path: item,
                        size: sz,
                        file_count: 1,
                        dir_count: 0,
                        children: vec![],
                        error: None,
                    });
                }
                Err(_) => continue,
            }
        } else if ft.is_dir() {
            dir_count += 1;
            stats.dirs += 1;
            let child_info = if opts.max_depth.is_none() || current_depth < opts.max_depth.unwrap_or(0)
            {
                scan_directory_inner(&item, opts, current_depth + 1, stats, progress)
            } else {
                let summary = get_dir_size(&item, stats, progress);
                DirInfo {
                    path: item,
                    size: summary.size,
                    file_count: summary.files,
                    dir_count: summary.dirs,
                    children: vec![],
                    error: summary.error,
                }
            };
            total_size += child_info.size;
            file_count += child_info.file_count;
            dir_count += child_info.dir_count;
            children.push(child_info);
        }
    }

    children.sort_by(|a, b| b.size.cmp(&a.size));
    DirInfo {
        path: path.to_path_buf(),
        size: total_size,
        file_count,
        dir_count,
        children,
        error,
    }
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
