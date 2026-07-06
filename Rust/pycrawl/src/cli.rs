use std::path::PathBuf;
use std::time::Instant;

use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};

use crate::crawl::{crawl_and_download, list_asset_urls, CrawlOptions};
use crate::wayback::crawl_and_download_wayback;

#[derive(Parser)]
#[command(
    name = "pycrawl",
    about = "Web crawler to download files from index pages (Rust port of Python/pycrawl)",
    version
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Crawl URL(s) and download matching files
    Run(RunArgs),
    /// Crawl URL(s) and print file URLs (dry run)
    ListUrls(ListUrlsArgs),
}

#[derive(Parser)]
pub struct RunArgs {
    /// Start URL to crawl
    pub url: String,

    #[arg(short = 'o', long = "out", default_value = "downloads")]
    pub out: PathBuf,

    #[arg(short = 'f', long = "follow")]
    pub follow: Option<String>,

    #[arg(short = 'e', long = "extensions", default_value = "pdf")]
    pub extensions: String,

    #[arg(short = 'd', long = "delay", default_value_t = 0.5)]
    pub delay: f64,

    #[arg(long)]
    pub overwrite: bool,

    #[arg(long = "no-subdirs", alias = "flat")]
    pub no_subdirs: bool,

    #[arg(short = 'c', long = "cookie")]
    pub cookie: Option<String>,

    #[arg(long = "wayback-from")]
    pub wayback_from: Option<String>,

    #[arg(long = "wayback-out")]
    pub wayback_out: Option<PathBuf>,
}

#[derive(Parser)]
pub struct ListUrlsArgs {
    pub url: String,

    #[arg(short = 'f', long = "follow")]
    pub follow: Option<String>,

    #[arg(short = 'e', long = "extensions", default_value = "pdf")]
    pub extensions: String,

    #[arg(short = 'c', long = "cookie")]
    pub cookie: Option<String>,
}

fn parse_extensions(spec: &str) -> Vec<String> {
    spec.split(',')
        .map(|s| {
            let t = s.trim().trim_start_matches('.');
            format!(".{t}")
        })
        .filter(|s| s.len() > 1)
        .collect()
}

pub async fn run_crawl(args: RunArgs) -> Result<u8> {
    if let Some(ref wb) = args.wayback_from {
        if !wb.chars().all(|c| c.is_ascii_digit()) || wb.len() != 8 {
            bail!("--wayback-from must be YYYYMMDD (e.g. 20250101)");
        }
    }

    let extensions = parse_extensions(&args.extensions);
    if extensions.is_empty() {
        bail!("no valid extensions specified");
    }

    let use_subdirs = args.follow.is_some() && !args.no_subdirs;
    let opts = CrawlOptions {
        follow_pattern: args.follow,
        extensions,
        delay_sec: args.delay,
        overwrite: args.overwrite,
        use_subdirs,
        cookie: args.cookie,
    };

    let started = Instant::now();
    let time_started = chrono_now();

    let (followed, downloaded, failed) = if let Some(from_date) = args.wayback_from {
        let wayback_out = args
            .wayback_out
            .unwrap_or_else(|| {
                let name = args.out.file_name().and_then(|s| s.to_str()).unwrap_or("downloads");
                args.out
                    .parent()
                    .unwrap_or(std::path::Path::new("."))
                    .join(format!("{name}_wayback"))
            });
        tokio::fs::create_dir_all(&wayback_out)
            .await
            .with_context(|| format!("create {}", wayback_out.display()))?;
        let result = crawl_and_download_wayback(&args.url, &wayback_out, &from_date, &opts).await?;
        println!("Saved to: {}", wayback_out.display());
        result
    } else {
        tokio::fs::create_dir_all(&args.out)
            .await
            .with_context(|| format!("create {}", args.out.display()))?;
        crawl_and_download(&args.url, &args.out, &opts).await?
    };

    print_summary(
        &followed,
        &downloaded,
        &failed,
        &time_started,
        started.elapsed(),
        args.wayback_from.is_some(),
    );
    Ok(0)
}

pub async fn run_list_urls(args: ListUrlsArgs) -> Result<u8> {
    let extensions = parse_extensions(&args.extensions);
    let opts = CrawlOptions {
        follow_pattern: args.follow,
        extensions,
        delay_sec: 0.3,
        overwrite: false,
        use_subdirs: false,
        cookie: args.cookie,
    };
    let urls = list_asset_urls(&args.url, &opts).await?;
    for url in urls {
        println!("{url}");
    }
    Ok(0)
}

fn print_summary(
    followed: &[String],
    downloaded: &[String],
    failed: &[String],
    time_started: &str,
    elapsed: std::time::Duration,
    wayback: bool,
) {
    let elapsed_str = if elapsed.as_secs() >= 1 {
        format!("{}s", elapsed.as_secs())
    } else {
        format!("{:.2}s", elapsed.as_secs_f64())
    };
    let title = if wayback {
        "Wayback crawl complete"
    } else {
        "Crawl complete"
    };
    println!("\n=== {title} ===");
    println!("Pages crawled: {}", followed.len());
    println!("Files downloaded: {}", downloaded.len());
    println!("Failed: {}", failed.len());
    println!("Time started: {time_started}");
    println!(
        "Time completed: {}",
        chrono_now()
    );
    println!("Time elapsed: {elapsed_str}");
    if !failed.is_empty() {
        println!("Failed URLs (first 10):");
        for url in failed.iter().take(10) {
            println!("  {url}");
        }
        if failed.len() > 10 {
            println!("  ... and {} more.", failed.len() - 10);
        }
    }
    if followed.is_empty() {
        println!(
            "No pages were crawled. The start URL may have failed to load \
             (check URL, cookie, or try in browser)."
        );
    }
}

fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let rem = secs % 86_400;
    format!(
        "{:02}:{:02}:{:02}",
        rem / 3600,
        (rem % 3600) / 60,
        rem % 60
    )
}
