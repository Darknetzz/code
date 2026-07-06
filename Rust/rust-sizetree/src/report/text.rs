use std::path::Path;

use crate::models::{
    dir_info_to_json_dict, format_size, iter_child_rows, DirInfo, ReportFormat,
};

pub fn write_scan_report(
    dir_info: &DirInfo,
    target_path: &Path,
    out_path: &Path,
    fmt: ReportFormat,
    tree_view: bool,
    limit: usize,
) -> anyhow::Result<()> {
    let text = match fmt {
        ReportFormat::Json => render_json(dir_info, target_path),
        ReportFormat::Markdown => render_markdown(dir_info, target_path, tree_view, limit),
        ReportFormat::Html => super::html::render_report_html(dir_info, target_path, limit),
        ReportFormat::Text => render_text(dir_info, target_path, tree_view, limit),
    };
    if let Some(parent) = out_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    std::fs::write(out_path, text)?;
    Ok(())
}

fn now_iso() -> String {
    chrono::Local::now()
        .format("%Y-%m-%dT%H:%M:%S")
        .to_string()
}

fn render_json(dir_info: &DirInfo, target_path: &Path) -> String {
    let payload = serde_json::json!({
        "scanned_path": target_path.display().to_string(),
        "generated_at": now_iso(),
        "root": dir_info_to_json_dict(dir_info),
    });
    serde_json::to_string_pretty(&payload).unwrap_or_else(|_| "{}".to_string()) + "\n"
}

fn render_text(
    dir_info: &DirInfo,
    target_path: &Path,
    tree_view: bool,
    limit: usize,
) -> String {
    let mut lines = vec![
        format!("Scan: {}", target_path.display()),
        format!("Generated: {}", now_iso()),
        String::new(),
        format!("Total Size: {}", format_size(dir_info.size)),
        format!(
            "Files: {} | Directories: {}",
            dir_info.file_count, dir_info.dir_count
        ),
        String::new(),
    ];
    if tree_view {
        lines.extend(build_plain_tree_lines(dir_info, limit, 3));
    } else {
        lines.extend(build_plain_table_lines(dir_info, target_path, limit));
    }
    lines.join("\n") + "\n"
}

fn render_markdown(
    dir_info: &DirInfo,
    target_path: &Path,
    tree_view: bool,
    limit: usize,
) -> String {
    let mut lines = vec![
        format!("# Disk usage: `{}`", target_path.display()),
        String::new(),
        format!("- **Total size:** {}", format_size(dir_info.size)),
        format!(
            "- **Files:** {} · **Directories:** {}",
            dir_info.file_count, dir_info.dir_count
        ),
        String::new(),
    ];
    if tree_view {
        lines.push("## Tree".to_string());
        lines.push(String::new());
        lines.push("```".to_string());
        lines.extend(build_plain_tree_lines(dir_info, limit, 3));
        lines.push("```".to_string());
    } else {
        lines.push("## Largest items".to_string());
        lines.push(String::new());
        lines.push("| # | Name | Size | Files | Dirs | Type |".to_string());
        lines.push("|---:|------|-----:|------:|-----:|------|".to_string());
        for row in iter_child_rows(dir_info, limit) {
            let item_type = if row.is_dir { "Dir" } else { "File" };
            let safe_name = row.child.name().replace('|', "\\|");
            lines.push(format!(
                "| {} | {} | {} | {} | {} | {} |",
                row.index, safe_name, row.size_str, row.files_str, row.dirs_str, item_type
            ));
        }
    }
    lines.join("\n") + "\n"
}

pub(crate) fn build_plain_tree_lines(
    dir_info: &DirInfo,
    limit: usize,
    max_level: u32,
) -> Vec<String> {
    let mut lines = Vec::new();
    fn walk(
        d: &DirInfo,
        prefix: &str,
        level: u32,
        limit: usize,
        max_level: u32,
        lines: &mut Vec<String>,
    ) {
        if level >= max_level {
            return;
        }
        let children: Vec<_> = d.children.iter().take(limit).collect();
        for (i, child) in children.iter().enumerate() {
            let is_last = i + 1 == children.len();
            let branch = if is_last { "└── " } else { "├── " };
            let err = child
                .error
                .as_ref()
                .map(|e| format!(" [Error: {e}]"))
                .unwrap_or_default();
            lines.push(format!(
                "{prefix}{branch}{} ({}){err}",
                child.name(),
                format_size(child.size)
            ));
            let ext = if is_last { "    " } else { "│   " };
            if !child.children.is_empty() {
                walk(child, &format!("{prefix}{ext}"), level + 1, limit, max_level, lines);
            }
        }
    }
    let root_err = dir_info
        .error
        .as_ref()
        .map(|e| format!(" [Error: {e}]"))
        .unwrap_or_default();
    lines.push(format!(
        "{} ({}){root_err}",
        dir_info.name(),
        format_size(dir_info.size)
    ));
    walk(dir_info, "", 0, limit, max_level, &mut lines);
    lines
}

fn build_plain_table_lines(dir_info: &DirInfo, target_path: &Path, limit: usize) -> Vec<String> {
    let mut lines = vec![
        format!("Largest Items in {}", target_path.display()),
        String::new(),
        format!(
            "{:>4}  {:<42}  {:>12}  {:>8}  {:>6}  Type",
            "#", "Name", "Size", "Files", "Dirs"
        ),
        "-".repeat(92),
    ];
    for row in iter_child_rows(dir_info, limit) {
        let item_type = if row.is_dir { "Dir" } else { "File" };
        let name = if row.child.name().len() > 42 {
            format!("{}...", &row.child.name()[..39])
        } else {
            row.child.name()
        };
        lines.push(format!(
            "{:>4}  {:<42}  {:>12}  {:>8}  {:>6}  {}",
            row.index, name, row.size_str, row.files_str, row.dirs_str, item_type
        ));
    }
    lines
}
