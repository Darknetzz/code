use std::path::Path;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use csv::Writer;
use reqwest::Client;
use serde_json::Value;
use tokio::fs;

use crate::crawl::{
    build_client, collect_pages_and_assets, download_file, filename_from_url, subdir_from_page_url,
    CrawlOptions,
};

const CDX_API: &str = "https://web.archive.org/cdx/search/cdx";
const WAYBACK_BASE: &str = "https://web.archive.org/web";

pub async fn crawl_and_download_wayback(
    start_url: &str,
    wayback_out: &Path,
    from_date: &str,
    opts: &CrawlOptions,
) -> Result<(Vec<String>, Vec<String>, Vec<String>)> {
    let referer = url::Url::parse(start_url)
        .ok()
        .map(|u| format!("{}://{}/", u.scheme(), u.host_str().unwrap_or("")));
    let client = build_client(opts, referer.as_deref())?;

    let (followed, unique_downloads) = collect_pages_and_assets(start_url, opts).await?;
    let total = unique_downloads.len();
    let mut downloaded = Vec::new();
    let mut failed = Vec::new();
    let mut capture_metadata: Vec<(String, String, String)> = Vec::new();

    for (idx, (page_url, asset_url)) in unique_downloads.into_iter().enumerate() {
        println!(
            "  [{}/{}] {}",
            idx + 1,
            total,
            filename_from_url(&asset_url)
        );
        let timestamp = match get_wayback_first_timestamp(&client, &asset_url, from_date, 0.3).await
        {
            Some(ts) => ts,
            None => {
                failed.push(asset_url);
                tokio::time::sleep(Duration::from_secs_f64(opts.delay_sec)).await;
                continue;
            }
        };
        let wayback_url = wayback_download_url(&asset_url, &timestamp);
        let subdir = if opts.use_subdirs {
            subdir_from_page_url(&page_url)
        } else {
            String::new()
        };
        let name = filename_from_url(&asset_url);
        let ext = std::path::Path::new(&name)
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| format!(".{e}"))
            .unwrap_or_default();
        let dest = if subdir.is_empty() {
            wayback_out.join(&name)
        } else {
            wayback_out.join(&subdir).join(&name)
        };
        match download_file(
            &client,
            &wayback_url,
            &dest,
            opts.overwrite,
            if ext.is_empty() { None } else { Some(&ext) },
        )
        .await
        {
            Ok(true) => {
                set_file_mtime_from_wayback(&dest, &timestamp).await;
                downloaded.push(asset_url.clone());
                let rel = dest
                    .strip_prefix(wayback_out)
                    .unwrap_or(dest.as_path())
                    .to_string_lossy()
                    .replace('\\', "/");
                capture_metadata.push((rel, asset_url, timestamp));
            }
            _ => failed.push(asset_url),
        }
        tokio::time::sleep(Duration::from_secs_f64(opts.delay_sec)).await;
    }

    if !capture_metadata.is_empty() {
        write_manifest(wayback_out, &capture_metadata).await?;
    }

    Ok((followed, downloaded, failed))
}

async fn get_wayback_first_timestamp(
    client: &Client,
    url: &str,
    from_date: &str,
    delay_sec: f64,
) -> Option<String> {
    let result = async {
        let resp = client
            .get(CDX_API)
            .query(&[
                ("url", url),
                ("from", from_date),
                ("output", "json"),
                ("limit", "1"),
                ("reverse", "1"),
            ])
            .timeout(Duration::from_secs(15))
            .send()
            .await
            .ok()?;
        let data: Value = resp.json().await.ok()?;
        let rows = data.as_array()?;
        if rows.len() < 2 {
            return None;
        }
        rows.get(1)?
            .as_array()?
            .get(1)?
            .as_str()
            .map(str::to_string)
    }
    .await;
    tokio::time::sleep(Duration::from_secs_f64(delay_sec)).await;
    result
}

fn wayback_download_url(original_url: &str, timestamp: &str) -> String {
    format!("{WAYBACK_BASE}/{timestamp}id_/{original_url}")
}

async fn set_file_mtime_from_wayback(path: &Path, timestamp: &str) {
    if timestamp.len() < 14 {
        return;
    }
    let year: i32 = timestamp[0..4].parse().unwrap_or(0);
    let month: u32 = timestamp[4..6].parse().unwrap_or(1);
    let day: u32 = timestamp[6..8].parse().unwrap_or(1);
    let hour: u32 = timestamp[8..10].parse().unwrap_or(0);
    let min: u32 = timestamp[10..12].parse().unwrap_or(0);
    let sec: u32 = timestamp[12..14].parse().unwrap_or(0);
    if let Ok(dt) = chrono_from_ymd_hms(year, month, day, hour, min, sec) {
        let _ = filetime_set(path, dt).await;
    }
}

fn chrono_from_ymd_hms(y: i32, m: u32, d: u32, h: u32, min: u32, s: u32) -> Result<u64> {
    // Days from epoch approximation via standard library only
    let days = civil_days_since_epoch(y, m, d)?;
    Ok(days * 86_400 + u64::from(h) * 3600 + u64::from(min) * 60 + u64::from(s))
}

fn civil_days_since_epoch(y: i32, m: u32, d: u32) -> Result<u64> {
    if !(1..=12).contains(&m) || !(1..=31).contains(&d) {
        anyhow::bail!("invalid date");
    }
    let y = y as i64;
    let m = m as i64;
    let d = d as i64;
    let m_adj = if m <= 2 { m + 12 } else { m };
    let y_adj = if m <= 2 { y - 1 } else { y };
    let era = (if y_adj >= 0 { y_adj } else { y_adj - 399 }) / 400;
    let yoe = y_adj - era * 400;
    let doy = (153 * (m_adj - 3) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    Ok((era * 146097 + doe - 719468) as u64)
}

async fn filetime_set(path: &Path, secs: u64) -> Result<()> {
    let _ = (path, secs);
    // Best-effort: set modified time where supported
    #[cfg(unix)]
    {
        use std::os::unix::fs::FileTimesExt;
        let times = std::fs::File::open(path)
            .ok()
            .and_then(|f| {
                let t = std::time::UNIX_EPOCH + Duration::from_secs(secs);
                f.set_modified(t).ok()
            });
        let _ = times;
    }
    Ok(())
}

async fn write_manifest(wayback_out: &Path, rows: &[(String, String, String)]) -> Result<()> {
    let manifest = wayback_out.join("wayback_capture_dates.csv");
    let mut wtr = Writer::from_path(&manifest).context("create manifest")?;
    wtr.write_record(["file", "url", "capture_timestamp", "capture_date"])?;
    for (rel, url, ts) in rows {
        let date_str = if ts.len() >= 14 {
            format!(
                "{}-{}-{} {}:{}:{}",
                &ts[0..4],
                &ts[4..6],
                &ts[6..8],
                &ts[8..10],
                &ts[10..12],
                &ts[12..14]
            )
        } else {
            ts.clone()
        };
        wtr.write_record([rel, url, ts, &date_str])?;
    }
    wtr.flush()?;
    Ok(())
}

#[allow(dead_code)]
fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
