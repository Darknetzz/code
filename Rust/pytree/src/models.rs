use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DirInfo {
    pub path: PathBuf,
    pub size: u64,
    pub file_count: u64,
    pub dir_count: u64,
    pub children: Vec<DirInfo>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl DirInfo {
    pub fn name(&self) -> String {
        self.path
            .file_name()
            .and_then(|s| s.to_str())
            .map(str::to_string)
            .unwrap_or_else(|| self.path.display().to_string())
    }

    pub fn format_size(&self) -> String {
        format_size(self.size)
    }
}

pub fn format_size(size: u64) -> String {
    let mut size_f = size as f64;
    for unit in ["B", "KB", "MB", "GB", "TB"] {
        if size_f < 1024.0 {
            return format!("{size_f:.1} {unit}");
        }
        size_f /= 1024.0;
    }
    format!("{size_f:.1} PB")
}

pub fn entry_is_directory(info: &DirInfo) -> bool {
    info.path.is_dir() || !info.children.is_empty()
}

pub struct ChildRow<'a> {
    pub index: usize,
    pub child: &'a DirInfo,
    pub size_str: String,
    pub files_str: String,
    pub dirs_str: String,
    pub is_dir: bool,
}

pub fn iter_child_rows<'a>(dir_info: &'a DirInfo, limit: usize) -> Vec<ChildRow<'a>> {
    dir_info
        .children
        .iter()
        .take(limit)
        .enumerate()
        .map(|(i, child)| {
            let (files_s, dirs_s) = child_count_cells(child);
            ChildRow {
                index: i + 1,
                child,
                size_str: format_size(child.size),
                files_str: files_s,
                dirs_str: dirs_s,
                is_dir: entry_is_directory(child),
            }
        })
        .collect()
}

fn child_count_cells(info: &DirInfo) -> (String, String) {
    if !entry_is_directory(info) {
        return (String::new(), String::new());
    }
    (
        format!("{}", info.file_count),
        format!("{}", info.dir_count),
    )
}

#[derive(Default)]
pub struct ScanStats {
    pub files: u64,
    pub dirs: u64,
    pub size: u64,
}

pub struct DirSummary {
    pub size: u64,
    pub files: u64,
    pub dirs: u64,
    pub error: Option<String>,
}

pub fn dir_info_to_json_dict(d: &DirInfo) -> serde_json::Value {
    serde_json::json!({
        "path": d.path.display().to_string(),
        "name": d.name(),
        "size_bytes": d.size,
        "size_human": d.format_size(),
        "file_count": d.file_count,
        "dir_count": d.dir_count,
        "error": d.error,
        "children": d.children.iter().map(dir_info_to_json_dict).collect::<Vec<_>>(),
    })
}

pub fn infer_report_format(path: &Path) -> Option<ReportFormat> {
    match path.extension().and_then(|e| e.to_str()).unwrap_or("") {
        "json" => Some(ReportFormat::Json),
        "md" | "markdown" => Some(ReportFormat::Markdown),
        "html" | "htm" => Some(ReportFormat::Html),
        "txt" | "" => Some(ReportFormat::Text),
        _ => None,
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ReportFormat {
    Text,
    Json,
    Markdown,
    Html,
}

impl ReportFormat {
    pub fn extension(self) -> &'static str {
        match self {
            Self::Text => ".txt",
            Self::Json => ".json",
            Self::Markdown => ".md",
            Self::Html => ".html",
        }
    }
}
