use std::fs;
use std::path::Path;

use anyhow::Result;

use crate::models::{DirInfo, DirSummary, ScanStats};

pub fn scan_directory(path: &Path, max_depth: Option<u32>, current_depth: u32) -> Result<DirInfo> {
    let mut stats = ScanStats::default();
    Ok(scan_directory_inner(
        path,
        max_depth,
        current_depth,
        &mut stats,
    ))
}

fn scan_directory_inner(
    path: &Path,
    max_depth: Option<u32>,
    current_depth: u32,
    stats: &mut ScanStats,
) -> DirInfo {
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
            let child_info = if max_depth.is_none() || current_depth < max_depth.unwrap_or(0) {
                scan_directory_inner(&item, max_depth, current_depth + 1, stats)
            } else {
                let summary = get_dir_size(&item, stats);
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

pub fn get_dir_size(path: &Path, stats: &mut ScanStats) -> DirSummary {
    let mut summary = DirSummary {
        size: 0,
        files: 0,
        dirs: 0,
        error: None,
    };
    walk_dir_size(path, &mut summary, stats);
    summary
}

fn walk_dir_size(path: &Path, summary: &mut DirSummary, stats: &mut ScanStats) {
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
            walk_dir_size(&entry.path(), summary, stats);
        } else if ft.is_file() {
            if let Ok(meta) = entry.metadata() {
                let sz = meta.len();
                summary.size += sz;
                summary.files += 1;
                stats.files += 1;
                stats.size += sz;
            }
        }
    }
}
