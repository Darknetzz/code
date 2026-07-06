use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use comfy_table::{presets::UTF8_FULL, Cell, Table};

use crate::models::{
    dir_info_to_json_dict, format_size, infer_report_format, iter_child_rows, ReportFormat,
};
use crate::report::write_scan_report;
use crate::scan::scan_directory;

#[derive(Parser)]
#[command(
    name = "pytree",
    about = "Disk space analyzer (Rust port of Python/pytree scan + report)",
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
}

#[derive(Parser)]
pub struct ReportArgs {
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
}

pub fn run_scan(args: ScanArgs) -> Result<u8> {
    let target = args.path.canonicalize().unwrap_or(args.path.clone());
    if !target.is_dir() {
        bail!("not a directory: {}", target.display());
    }
    eprintln!("Scanning {} ...", target.display());
    let info = scan_directory(&target, args.depth, 0)?;
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
    let out = args
        .output
        .unwrap_or_else(|| default_report_path(&target, fmt));
    eprintln!("Scanning {} ...", target.display());
    let info = scan_directory(&target, args.depth, 0)?;
    write_scan_report(&info, &target, &out, fmt, args.tree, args.limit)?;
    println!("Report written to {}", out.display());
    Ok(0)
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

fn default_report_path(target: &Path, fmt: ReportFormat) -> PathBuf {
    let name = target
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("scan");
    PathBuf::from(format!("pytree-{name}{}", fmt.extension()))
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
