use std::fs;
use std::path::Path;

use anyhow::Result;

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
) -> Result<()> {
    let text = match fmt {
        ReportFormat::Json => render_json(dir_info, target_path),
        ReportFormat::Markdown => render_markdown(dir_info, target_path, tree_view, limit),
        ReportFormat::Html => render_html(dir_info, target_path, tree_view, limit),
        ReportFormat::Text => render_text(dir_info, target_path, tree_view, limit),
    };
    if let Some(parent) = out_path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    fs::write(out_path, text)?;
    Ok(())
}

fn now_iso() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{secs}")
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
        for line in build_plain_tree_lines(dir_info, limit, 3) {
            lines.push(format!("```\n{line}"));
        }
    } else {
        lines.push("## Largest items".to_string());
        lines.push(String::new());
        lines.push("| # | Name | Size | Files | Dirs | Type |".to_string());
        lines.push("|---:|------|-----:|------:|-----:|------|".to_string());
        for row in iter_child_rows(dir_info, limit) {
            let item_type = if row.is_dir { "Dir" } else { "File" };
            lines.push(format!(
                "| {} | {} | {} | {} | {} | {} |",
                row.index,
                row.child.name(),
                row.size_str,
                row.files_str,
                row.dirs_str,
                item_type
            ));
        }
    }
    lines.join("\n") + "\n"
}

fn render_html(
    dir_info: &DirInfo,
    target_path: &Path,
    tree_view: bool,
    limit: usize,
) -> String {
    let body = if tree_view {
        let tree = build_plain_tree_lines(dir_info, limit, 3)
            .into_iter()
            .map(|l| html_escape(&l))
            .collect::<Vec<_>>()
            .join("<br>\n");
        format!("<h2>Tree</h2><pre>{tree}</pre>")
    } else {
        let mut rows = String::new();
        for row in iter_child_rows(dir_info, limit) {
            let item_type = if row.is_dir { "Dir" } else { "File" };
            rows.push_str(&format!(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>\n",
                row.index,
                html_escape(&row.child.name()),
                html_escape(&row.size_str),
                html_escape(&row.files_str),
                html_escape(&row.dirs_str),
                item_type
            ));
        }
        format!(
            "<h2>Largest items</h2><table><thead><tr><th>#</th><th>Name</th><th>Size</th><th>Files</th><th>Dirs</th><th>Type</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    };
    format!(
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Disk usage: {}</title>\
         <style>body{{font-family:system-ui,sans-serif;margin:2rem}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:.4rem .6rem}}</style></head>\
         <body><h1>Disk usage: {}</h1><p>Total: {} · Files: {} · Dirs: {}</p>{body}\
         <footer><small>SizeTree / rust-sizetree</small></footer></body></html>\n",
        html_escape(&target_path.display().to_string()),
        html_escape(&target_path.display().to_string()),
        format_size(dir_info.size),
        dir_info.file_count,
        dir_info.dir_count,
    )
}

fn build_plain_tree_lines(dir_info: &DirInfo, limit: usize, max_level: u32) -> Vec<String> {
    let mut lines = Vec::new();
    fn walk(d: &DirInfo, prefix: &str, level: u32, limit: usize, max_level: u32, lines: &mut Vec<String>) {
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

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}
