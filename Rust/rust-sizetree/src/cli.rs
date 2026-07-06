use std::env;
use std::path::{Path, PathBuf};

use anyhow::{bail, Result};
use clap::{Parser, Subcommand};
use comfy_table::{presets::UTF8_FULL, Cell, Table};

use crate::browser::open_in_browser;
use crate::models::{format_size, infer_report_format, iter_child_rows, ReportFormat};
use crate::progress::ScanProgress;
use crate::report::write_scan_report;
use crate::scan::{scan_directory_with, ScanOptions};

#[derive(Parser)]
#[command(
    name = "rust-sizetree",
    about = "Disk space analyzer (scan + report)",
    version
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Scan a directory and print results to the terminal
    Scan(ScanArgs),
    /// Write an HTML/JSON/Markdown/text report file
    Report(ReportArgs),
    /// Show version information
    Version,
}

#[derive(Parser)]
pub struct ScanArgs {
    /// Directory to scan
    #[arg(default_value = ".")]
    pub path: PathBuf,

    #[arg(short = 'd', long = "depth")]
    pub depth: Option<u32>,

    #[arg(short = 'l', long = "limit", default_value_t = 20)]
    pub limit: usize,

    #[arg(short = 't', long = "tree")]
    pub tree: bool,

    /// Include hidden files and directories
    #[arg(long = "hidden")]
    pub hidden: bool,
}

#[derive(Parser)]
pub struct ReportArgs {
    /// Directory to scan
    #[arg(default_value = ".")]
    pub path: PathBuf,

    #[arg(short = 'o', long = "output")]
    pub output: Option<PathBuf>,

    #[arg(short = 'f', long = "format")]
    pub format: Option<String>,

    #[arg(short = 'd', long = "depth")]
    pub depth: Option<u32>,

    #[arg(short = 'l', long = "limit", default_value_t = 50)]
    pub limit: usize,

    #[arg(short = 't', long = "tree")]
    pub tree: bool,

    /// Include hidden files and directories
    #[arg(long = "hidden")]
    pub hidden: bool,

    /// Do not launch the browser for HTML reports
    #[arg(long = "no-open")]
    pub no_open: bool,
}

pub fn run_scan(args: ScanArgs) -> Result<u8> {
    let target = args.path.canonicalize().unwrap_or(args.path.clone());
    if !target.is_dir() {
        bail!("not a directory: {}", target.display());
    }
    eprintln!("Scanning: {}", target.display());
    let info = scan_with_progress(&target, args.depth, args.hidden)?;
    if args.tree {
        print_tree(&info, args.limit, 3);
    } else {
        print_table(&info, &target, args.limit);
    }
    println!();
    println!(
        "Total: {} | Files: {} | Directories: {}",
        format_size(info.size),
        info.file_count,
        info.dir_count
    );
    Ok(0)
}

pub fn run_report(args: ReportArgs) -> Result<u8> {
    let target = args.path.canonicalize().unwrap_or(args.path.clone());
    if !target.is_dir() {
        bail!("not a directory: {}", target.display());
    }
    let fmt = resolve_format(&args.output, args.format.as_deref())?;
    let is_temp = args.output.is_none();
    let out = args
        .output
        .unwrap_or_else(|| make_temp_report_path(&target, fmt));
    eprintln!("Scanning: {}", target.display());
    let info = scan_with_progress(&target, args.depth, args.hidden)?;
    write_scan_report(&info, &target, &out, fmt, args.tree, args.limit)?;
    let label = if is_temp { "Generated" } else { "Wrote" };
    println!("{label} {} report: {}", fmt.label(), out.display());

    if fmt == ReportFormat::Html && !args.no_open {
        if open_in_browser(&out) {
            eprintln!("Opened in your default browser.");
        } else {
            eprintln!("Could not launch a browser automatically; open the file above manually.");
        }
    }
    Ok(0)
}

fn scan_with_progress(
    target: &Path,
    depth: Option<u32>,
    hidden: bool,
) -> Result<crate::models::DirInfo> {
    let opts = ScanOptions {
        max_depth: depth,
        include_hidden: hidden,
    };
    let mut progress = ScanProgress::new();
    let info = scan_directory_with(target, &opts, 0, Some(&mut progress))?;
    progress.finish(&crate::models::ScanStats {
        files: info.file_count,
        dirs: info.dir_count,
        size: info.size,
        current: None,
    });
    eprintln!("Scan complete");
    Ok(info)
}

fn resolve_format(output: &Option<PathBuf>, format_flag: Option<&str>) -> Result<ReportFormat> {
    if let Some(s) = format_flag {
        return match s.to_lowercase().as_str() {
            "text" | "txt" => Ok(ReportFormat::Text),
            "json" => Ok(ReportFormat::Json),
            "markdown" | "md" => Ok(ReportFormat::Markdown),
            "html" | "htm" => Ok(ReportFormat::Html),
            other => bail!("unknown format: {other}"),
        };
    }
    if let Some(path) = output {
        if let Some(fmt) = infer_report_format(path) {
            return Ok(fmt);
        }
    }
    Ok(ReportFormat::Html)
}

fn slugify_for_filename(value: &str) -> String {
    let cleaned: String = value
        .chars()
        .map(|c| {
            if c.is_alphanumeric() || c == '-' || c == '_' || c == '.' {
                c
            } else {
                '_'
            }
        })
        .collect();
    let trimmed = cleaned.trim_matches(|c| c == '.' || c == '_');
    if trimmed.is_empty() {
        "root".to_string()
    } else {
        trimmed.chars().take(40).collect()
    }
}

fn make_temp_report_path(target_path: &Path, fmt: ReportFormat) -> PathBuf {
    let name = target_path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("root");
    let slug = slugify_for_filename(name);
    let stamp = chrono::Local::now().format("%Y%m%d-%H%M%S");
    env::temp_dir().join(format!(
        "rust-sizetree-{slug}-{stamp}{}",
        fmt.extension()
    ))
}

fn print_table(info: &crate::models::DirInfo, target: &Path, limit: usize) {
    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_header(vec!["#", "Name", "Size", "Files", "Dirs", "Type"]);
    for row in iter_child_rows(info, limit) {
        let name = if row.child.name().len() > 42 {
            format!("{}...", &row.child.name()[..39])
        } else {
            row.child.name()
        };
        let item_type = if row.is_dir { "Dir" } else { "File" };
        table.add_row(vec![
            Cell::new(row.index),
            Cell::new(name),
            Cell::new(row.size_str),
            Cell::new(row.files_str),
            Cell::new(row.dirs_str),
            Cell::new(item_type),
        ]);
    }
    println!("Largest items in {}", target.display());
    println!("{table}");
}

fn print_tree(info: &crate::models::DirInfo, limit: usize, max_level: u32) {
    let err = info
        .error
        .as_ref()
        .map(|e| format!(" [Error: {e}]"))
        .unwrap_or_default();
    println!("{} ({}){}", info.name(), format_size(info.size), err);
    print_tree_inner(info, "", 0, limit, max_level);
}

fn print_tree_inner(
    info: &crate::models::DirInfo,
    prefix: &str,
    level: u32,
    limit: usize,
    max_level: u32,
) {
    if level >= max_level {
        return;
    }
    let children: Vec<_> = info.children.iter().take(limit).collect();
    for (i, child) in children.iter().enumerate() {
        let is_last = i + 1 == children.len();
        let branch = if is_last { "└── " } else { "├── " };
        let err = child
            .error
            .as_ref()
            .map(|e| format!(" [Error: {e}]"))
            .unwrap_or_default();
        println!(
            "{prefix}{branch}{} ({}){}",
            child.name(),
            format_size(child.size),
            err
        );
        let ext = if is_last { "    " } else { "│   " };
        if !child.children.is_empty() {
            print_tree_inner(child, &format!("{prefix}{ext}"), level + 1, limit, max_level);
        }
    }
}
