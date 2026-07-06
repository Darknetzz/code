use std::f64::consts::PI;
use std::path::Path;

use crate::models::{entry_is_directory, format_count, format_size, html_escape, DirInfo};
use crate::report::icons::{btn_label, file_icon_key, icon, th_sort};

const CHART_COLORS: &[&str] = &[
    "#58a6ff", "#d2a8ff", "#79c0ff", "#3fb950", "#ffa657", "#f85149", "#a371f7", "#7ee787",
    "#ff7b72", "#d4a72c", "#79c0ff", "#db61a2",
];

const REPORT_CSS: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/report.css"));
const REPORT_TABLE_JS: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/report_table.js"));
const REPORT_VIZ_JS: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/report_viz.js"));

pub fn render_report_html(dir_info: &DirInfo, target_path: &Path, limit: usize) -> String {
    let path_s = target_path.display().to_string();
    let title_esc = html_escape(&format!("Disk usage - {path_s}"));
    let gen = html_escape(
        &chrono::Local::now()
            .format("%Y-%m-%dT%H:%M:%S")
            .to_string(),
    );
    let size_h = html_escape(&format_size(dir_info.size));
    let total_sz = dir_info.size.max(1);

    let viz_html = storage_viz_block(dir_info, limit);
    let rows = html_tree_rows(dir_info, limit, 28, "", 0, total_sz, 0);
    let table_body = if rows.is_empty() {
        "<tbody><tr><td colspan=\"6\" class=\"empty\">No items</td></tr></tbody>".to_string()
    } else {
        format!("<tbody>{}</tbody>", rows.join(""))
    };

    let root_line = format!(
        r#"<div class="tree-root-label"><strong>{}</strong> <span class="tree-meta">{}</span></div>"#,
        html_escape(&dir_info.name()),
        html_escape(&format_size(dir_info.size))
    );

    let table_section = format!(
        r##"<section class="panel" id="pytree-table-panel">
<h2>Contents</h2>
<p class="table-hint">Click column headers to sort <strong>top-level</strong> items (share = % of total scan). Click the caret next to a folder to open it; nested <strong>Share</strong> is % of that folder.</p>
<div class="tree-toolbar">
<div class="tree-filter-wrap">
<span class="tree-filter-icon">{}</span>
<input type="search" id="tree-filter" class="tree-filter" placeholder="Filter top-level by name..." autocomplete="off" spellcheck="false" />
</div>
<label class="toolbar-toggle" title="Always show folders before files when sorting">
<input type="checkbox" id="folders-first-cb">
<span class="btn-icon">{}</span>
Folders first
</label>
<button type="button" class="btn" id="tree-expand-all">{}</button>
<button type="button" class="btn" id="tree-collapse-all">{}</button>
<span class="tree-filter-status" id="tree-filter-status"></span>
</div>
<div class="table-wrap merged-tree-table">
{root_line}
<table id="pytree-items">
<colgroup>
<col class="col-w-idx"><col class="col-w-name"><col class="col-w-share"><col class="col-w-size"><col class="col-w-files"><col class="col-w-dirs">
</colgroup>
<thead><tr>
<th class="num">#</th>
{}
{}
{}
{}
{}
</tr></thead>
{table_body}
</table></div></section>"##,
        icon("search", 14, "chrome-icon"),
        icon("folder_up", 13, "chrome-icon"),
        btn_label("expand_all", "Expand all"),
        btn_label("collapse_all", "Collapse all"),
        th_sort("name", "Name", "label", ""),
        th_sort("pct", "Share", "pie", ""),
        th_sort("size", "Size", "disk", "sort-desc"),
        th_sort("files", "Files", "file", ""),
        th_sort("dirs", "Dirs", "dir", ""),
    );

    let body = format!(
        r#"<div class="layout">
<section class="panel panel-viz"><h2>Storage overview</h2>{viz_html}</section>
{table_section}
</div>
"#
    );

    let summary = format!(
        r#"<header class="hero">
<h1>{title_esc}</h1>
<dl class="meta">
<dt>Path</dt><dd><code>{}</code></dd>
<dt>Generated</dt><dd>{gen}</dd>
<dt>Total size</dt><dd class="stat-big">{size_h}</dd>
<dt>Contents</dt><dd>{} files &middot; {} directories</dd>
</dl>
</header>
"#,
        html_escape(&path_s),
        format_count(dir_info.file_count),
        format_count(dir_info.dir_count),
    );

    format!(
        r#"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc}</title>
<style>
{REPORT_CSS}
</style>
</head>
<body>
<div class="wrap">
{summary}{body}
<footer>SizeTree / rust-sizetree disk usage report</footer>
</div>
{REPORT_TABLE_JS}
{REPORT_VIZ_JS}
</body>
</html>
"#
    )
}

fn heat_bg(value: u64, max_value: u64) -> String {
    if max_value == 0 || value == 0 {
        return String::new();
    }
    let ratio = (value as f64 / max_value as f64).clamp(0.0, 1.0);
    let curved = ratio.sqrt();
    let hue = 120.0 * (1.0 - curved);
    let alpha = 0.12 + 0.38 * curved;
    format!("hsla({hue:.0}, 72%, 45%, {alpha:.3})")
}

fn pill(value_html: &str, bg: &str) -> String {
    if bg.is_empty() {
        format!(r#"<span class="heat-pill heat-pill-zero">{value_html}</span>"#)
    } else {
        format!(r#"<span class="heat-pill" style="background:{bg}">{value_html}</span>"#)
    }
}

fn html_tree_rows(
    parent: &DirInfo,
    limit: usize,
    max_depth: usize,
    path_id: &str,
    depth: usize,
    share_base: u64,
    color_offset: usize,
) -> Vec<String> {
    if depth >= max_depth {
        return Vec::new();
    }

    let base = share_base.max(1);
    let kids: Vec<_> = parent.children.iter().take(limit).collect();
    let max_size = kids.iter().map(|c| c.size).max().unwrap_or(0);
    let max_files = kids.iter().map(|c| c.file_count).max().unwrap_or(0);
    let max_dirs = kids.iter().map(|c| c.dir_count).max().unwrap_or(0);

    let mut rows = Vec::new();
    for (i, child) in kids.iter().enumerate() {
        let is_dir = entry_is_directory(child);
        let kind = if is_dir { "dir" } else { "file" };
        let pct = 100.0 * child.size as f64 / base as f64;
        let bar_color = CHART_COLORS[(color_offset + i) % CHART_COLORS.len()];

        let child_path = if path_id.is_empty() {
            i.to_string()
        } else {
            format!("{path_id}.{i}")
        };
        let has_kids = is_dir && (depth + 1 < max_depth) && !child.children.is_empty();
        let is_top = depth == 0;
        let idx_html = if is_top { format!("{}", i + 1) } else { String::new() };
        let idx_cell = format!(r#"<td class="num col-idx">{idx_html}</td>"#);

        let expand_html = if has_kids {
            r#"<button type="button" class="row-expand" aria-expanded="false" aria-label="Toggle folder contents"></button>"#
        } else {
            r#"<span class="row-expand-placeholder"></span>"#
        };
        let icon_key = if is_dir {
            "dir"
        } else {
            file_icon_key(&child.name())
        };
        let icon_html = format!(
            r#"<span class="entry-icon" data-kind="{kind}" data-icon="{icon_key}">{}</span>"#,
            icon(icon_key, 14, "icon-svg")
        );
        let name_inner = format!(
            r#"{expand_html}{icon_html}<span class="entry-name">{}</span>"#,
            html_escape(&child.name())
        );

        let size_pill = pill(&html_escape(&format_size(child.size)), &heat_bg(child.size, max_size));
        let (files_pill, dirs_pill) = if is_dir {
            (
                pill(
                    &format_count(child.file_count),
                    &heat_bg(child.file_count, max_files),
                ),
                pill(
                    &format_count(child.dir_count),
                    &heat_bg(child.dir_count, max_dirs),
                ),
            )
        } else {
            // Files: muted dash keeps pill column rhythm (dirs use heat-pill-zero for 0).
            (pill("—", ""), pill("—", ""))
        };

        let indent_rem = 0.75 + depth as f64 * 1.25;
        let hidden_attr = if is_top { "" } else { " hidden" };
        let viz_idx_attr = if is_top {
            format!(r#" data-viz-idx="{i}""#)
        } else {
            String::new()
        };

        let bar_w = pct.min(100.0);

        rows.push(format!(
            r#"<tr class="item-row depth-{depth}" data-path="{child_path}" data-parent="{path_id}" data-depth="{depth}" data-is-dir="{}" data-has-kids="{}" data-sort-name="{}" data-size="{}" data-files="{}" data-dirs="{}" data-kind="{}" data-pct="{pct:.6}"{viz_idx_attr}{hidden_attr}>{idx_cell}<td class="name" style="padding-left:{indent_rem:.2}rem">{name_inner}</td><td class="share-cell"><div class="share-bar" title="{pct:.1}%"><span style="width:{bar_w:.4}%;background:{bar_color}"></span></div><span class="share-pct">{pct:.1}%</span></td><td class="num size">{size_pill}</td><td class="num">{files_pill}</td><td class="num">{dirs_pill}</td></tr>"#,
            if is_dir { 1 } else { 0 },
            if has_kids { 1 } else { 0 },
            html_escape(&child.name()),
            child.size,
            child.file_count,
            child.dir_count,
            if is_dir { 0 } else { 1 },
        ));

        if has_kids {
            rows.extend(html_tree_rows(
                child,
                limit,
                max_depth,
                &child_path,
                depth + 1,
                child.size.max(1),
                color_offset + i + 1,
            ));
        }
    }
    rows
}

fn svg_donut_slices(segments: &[(u64, &str, usize)], total: u64) -> String {
    if total == 0 || segments.is_empty() {
        return String::new();
    }
    let cx = 100.0;
    let cy = 100.0;
    let outer_r = 78.0;
    let inner_r = 44.0;
    let mut start = -PI / 2.0;
    let mut paths = String::new();
    for &(size, color, viz_idx) in segments {
        if size == 0 {
            continue;
        }
        let sweep = 2.0 * PI * (size as f64 / total as f64);
        let a0 = start;
        let a1 = start + sweep;
        let x0o = cx + outer_r * a0.cos();
        let y0o = cy + outer_r * a0.sin();
        let x1o = cx + outer_r * a1.cos();
        let y1o = cy + outer_r * a1.sin();
        let x0i = cx + inner_r * a0.cos();
        let y0i = cy + inner_r * a0.sin();
        let x1i = cx + inner_r * a1.cos();
        let y1i = cy + inner_r * a1.sin();
        let large = if sweep > PI { 1 } else { 0 };
        paths.push_str(&format!(
            r##"<path class="viz-donut-seg" data-viz-idx="{viz_idx}" tabindex="0" d="M {x0o:.2} {y0o:.2} A {outer_r} {outer_r} 0 {large} 1 {x1o:.2} {y1o:.2} L {x1i:.2} {y1i:.2} A {inner_r} {inner_r} 0 {large} 0 {x0i:.2} {y0i:.2} Z" fill="{color}" stroke="#0d1117" stroke-width="1"/>"##
        ));
        start = a1;
    }
    paths
}

fn storage_viz_block(dir_info: &DirInfo, limit: usize) -> String {
    let kids: Vec<_> = dir_info
        .children
        .iter()
        .take(limit.max(24))
        .collect();
    let total = dir_info.size.max(1);
    if kids.is_empty() {
        return r#"<p class="viz-empty">No direct items to chart.</p>"#.to_string();
    }

    let chart_items: Vec<_> = kids
        .iter()
        .enumerate()
        .map(|(i, ch)| {
            (
                ch.name(),
                ch.size,
                CHART_COLORS[i % CHART_COLORS.len()],
            )
        })
        .collect();

    let seg_data: Vec<_> = chart_items
        .iter()
        .enumerate()
        .map(|(i, (_, sz, col))| (*sz, *col, i))
        .collect();
    let paths = svg_donut_slices(&seg_data, total);

    let viz_payload: Vec<serde_json::Value> = kids
        .iter()
        .enumerate()
        .map(|(i, ch)| {
            let is_dir = entry_is_directory(ch);
            let col = CHART_COLORS[i % CHART_COLORS.len()];
            let mut obj = serde_json::json!({
                "i": i,
                "name": ch.name(),
                "size": ch.size,
                "human": format_size(ch.size),
                "isDir": is_dir,
                "color": col,
                "pctRoot": (100.0 * ch.size as f64 / total as f64 * 10000.0).round() / 10000.0,
            });
            if is_dir {
                obj["files"] = serde_json::json!(ch.file_count);
                obj["dirs"] = serde_json::json!(ch.dir_count);
            } else {
                obj["files"] = serde_json::Value::Null;
                obj["dirs"] = serde_json::Value::Null;
            }
            obj
        })
        .collect();
    let json_text = serde_json::to_string(&viz_payload).unwrap_or_else(|_| "[]".to_string());
    let json_text = json_text.replace("</", "<\\/");

    let legend_rows: String = chart_items
        .iter()
        .enumerate()
        .map(|(i, (name, size, color))| {
            let pct = 100.0 * *size as f64 / total as f64;
            format!(
                r#"<label class="legend-row viz-legend-row" data-viz-idx="{i}"><input type="checkbox" class="viz-filter-cb" data-viz-idx="{i}" checked aria-label="Include in chart"/><span class="swatch" style="background:{color}"></span><span class="legend-name">{}</span><span class="legend-pct">{pct:.1}%</span><span class="legend-sz">{}</span></label>"#,
                html_escape(name),
                html_escape(&format_size(*size))
            )
        })
        .collect::<Vec<_>>()
        .join("\n");

    let stacked_parts: String = chart_items
        .iter()
        .enumerate()
        .map(|(i, (_, size, color))| {
            let w = 100.0 * *size as f64 / total as f64;
            format!(
                r#"<span class="viz-hbar-seg" data-viz-idx="{i}" style="width:{w:.3}%;background:{color}"></span>"#
            )
        })
        .collect();

    format!(
        r#"<div class="storage-viz" id="pytree-storage-viz">
<script type="application/json" id="pytree-viz-data">{json_text}</script>
<div class="viz-toolbar-wrap"><div class="viz-toolbar">
<button type="button" class="btn viz-tb-btn" id="viz-show-all" title="Include every item in the chart">{show_all}</button>
<button type="button" class="btn viz-tb-btn" id="viz-hide-all" title="Hide every segment (chart empty)">{hide_all}</button>
<span class="viz-status" id="viz-filter-status"></span>
</div></div>
<div id="pytree-viz-tooltip" class="viz-tooltip" hidden></div>
<div class="storage-viz-top">
<div class="donut-wrap" id="pytree-donut-wrap">
<svg viewBox="0 0 200 200" class="donut-svg" id="pytree-donut-svg" role="img" aria-label="Storage share by item">
<defs><filter id="pytree-donut-glow"><feGaussianBlur stdDeviation="0.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
<g id="pytree-donut-paths">{paths}</g>
</svg>
<p class="viz-donut-empty" id="pytree-donut-empty" hidden>No segments visible — enable items below.</p>
</div>
<div class="viz-charts-col"><h3 class="viz-title">Share of scanned folder</h3>
<div class="stacked-hbar" id="pytree-stacked-hbar" role="img" aria-label="Relative size of each item">{stacked_parts}</div>
</div>
</div>
<div class="legend-col legend-col-full">{legend_rows}</div>
</div>"#,
        show_all = btn_label("eye", "Show all"),
        hide_all = btn_label("eye_slash", "Hide all"),
    )
}
