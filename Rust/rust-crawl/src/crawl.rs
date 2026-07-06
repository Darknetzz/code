use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result};
use regex::Regex;
use reqwest::header::{COOKIE, REFERER, USER_AGENT};
use reqwest::Client;
use scraper::{Html, Selector};
use tokio::io::AsyncWriteExt;
use url::Url;

pub const DEFAULT_USER_AGENT: &str =
    "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0";

pub struct CrawlOptions {
    pub follow_pattern: Option<String>,
    pub extensions: Vec<String>,
    pub delay_sec: f64,
    pub overwrite: bool,
    pub use_subdirs: bool,
    pub cookie: Option<String>,
}

pub fn build_client(opts: &CrawlOptions, referer: Option<&str>) -> Result<Client> {
    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert(
        USER_AGENT,
        DEFAULT_USER_AGENT.parse().context("user agent header")?,
    );
    if let Some(cookie) = &opts.cookie {
        headers.insert(COOKIE, cookie.parse().context("cookie header")?);
    }
    if let Some(ref_url) = referer {
        headers.insert(REFERER, ref_url.parse().context("referer header")?);
    }
    Client::builder()
        .default_headers(headers)
        .timeout(Duration::from_secs(30))
        .build()
        .context("build HTTP client")
}

pub async fn fetch_html(client: &Client, url: &str) -> Option<String> {
    match client.get(url).send().await {
        Ok(resp) if resp.status().is_success() => resp.text().await.ok(),
        _ => None,
    }
}

pub fn extract_links(
    html: &str,
    base_url: &str,
    follow_re: Option<&Regex>,
    extensions: &[String],
    download_re: Option<&Regex>,
) -> (Vec<String>, Vec<String>) {
    let document = Html::parse_document(html);
    let selector = Selector::parse("a[href]").expect("valid selector");
    let base = Url::parse(base_url).ok();

    let mut to_follow = Vec::new();
    let mut to_download = Vec::new();

    for el in document.select(&selector) {
        let href = el.value().attr("href").unwrap_or("").trim();
        if href.is_empty() || href.starts_with('#') || href.starts_with("mailto:") {
            continue;
        }
        let full = match base.as_ref().and_then(|b| b.join(href).ok()) {
            Some(u) => u.to_string(),
            None => continue,
        };
        let path_lower = Url::parse(&full)
            .map(|u| u.path().to_lowercase())
            .unwrap_or_default();

        if let Some(re) = follow_re {
            if re.is_match(&full) {
                to_follow.push(full);
                continue;
            }
        }

        if extensions.is_empty() {
            continue;
        }
        if !extensions
            .iter()
            .any(|ext| path_lower.ends_with(&ext.to_lowercase()))
        {
            continue;
        }
        if let Some(re) = download_re {
            if !re.is_match(&full) {
                continue;
            }
        }
        to_download.push(full);
    }

    (dedupe(to_follow), dedupe(to_download))
}

fn dedupe(mut items: Vec<String>) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    items.retain(|item| seen.insert(item.clone()));
    items
}

pub fn filename_from_url(url: &str) -> String {
    Url::parse(url)
        .ok()
        .map(|u| {
            let path = u.path().trim_end_matches('/');
            path.rsplit('/').next().unwrap_or("index").to_string()
        })
        .unwrap_or_else(|| "index".to_string())
}

pub fn subdir_from_page_url(page_url: &str) -> String {
    Url::parse(page_url)
        .ok()
        .map(|u| {
            let path = u.path().trim_end_matches('/');
            path.rsplit('/').next().unwrap_or("index").to_string()
        })
        .unwrap_or_else(|| "index".to_string())
}

fn response_matches_extension(ext: &str, content_type: Option<&str>, first_bytes: &[u8]) -> bool {
    let ext = ext.to_lowercase();
    if ext == ".pdf" {
        if first_bytes.starts_with(b"%PDF-") {
            return true;
        }
        if let Some(ct) = content_type {
            let ct = ct.split(';').next().unwrap_or("").trim().to_lowercase();
            if ct == "application/pdf" || ct == "application/octet-stream" {
                return true;
            }
        }
        return false;
    }
    if ext == ".zip" {
        return first_bytes.starts_with(b"PK");
    }
    true
}

pub async fn download_file(
    client: &Client,
    url: &str,
    dest: &Path,
    overwrite: bool,
    expected_extension: Option<&str>,
) -> Result<bool> {
    if dest.exists() && !overwrite {
        return Ok(true);
    }
    let mut resp = client
        .get(url)
        .send()
        .await
        .with_context(|| format!("GET {url}"))?
        .error_for_status()
        .with_context(|| format!("HTTP error for {url}"))?;

    let content_type = resp
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .map(str::to_string);

    let mut first_chunk = Vec::new();
    if let Some(chunk) = resp.chunk().await? {
        first_chunk.extend_from_slice(&chunk);
    }

    if let Some(ext) = expected_extension {
        if !response_matches_extension(ext, content_type.as_deref(), &first_chunk) {
            return Ok(false);
        }
    }

    if let Some(parent) = dest.parent() {
        tokio::fs::create_dir_all(parent).await?;
    }
    let mut file = tokio::fs::File::create(dest).await?;
    file.write_all(&first_chunk).await?;
    while let Some(chunk) = resp.chunk().await? {
        file.write_all(&chunk).await?;
    }
    file.flush().await?;
    Ok(true)
}

pub async fn collect_pages_and_assets(
    start_url: &str,
    opts: &CrawlOptions,
) -> Result<(Vec<String>, Vec<(String, String)>)> {
    let referer = Url::parse(start_url)
        .ok()
        .map(|u| format!("{}://{}/", u.scheme(), u.host_str().unwrap_or("")));
    let client = build_client(opts, referer.as_deref())?;

    if let Ok(resp) = client.get(start_url).send().await {
        if !resp.status().is_success() {
            eprintln!(
                "Start URL returned HTTP {} {}",
                resp.status().as_u16(),
                resp.status().canonical_reason().unwrap_or("")
            );
        }
    }

    let follow_re = opts
        .follow_pattern
        .as_ref()
        .map(|p| Regex::new(p))
        .transpose()
        .context("invalid --follow regex")?;

    let mut pages = vec![start_url.to_string()];
    if follow_re.is_some() {
        if let Some(html) = fetch_html(&client, start_url).await {
            let (to_follow, _) =
                extract_links(&html, start_url, follow_re.as_ref(), &[], None);
            pages.extend(to_follow);
        }
        tokio::time::sleep(delay(opts.delay_sec)).await;
    }

    let mut followed = Vec::new();
    let mut to_download = Vec::new();

    for page_url in pages {
        if page_url != start_url {
            tokio::time::sleep(delay(opts.delay_sec)).await;
        }
        let Some(html) = fetch_html(&client, &page_url).await else {
            continue;
        };
        let (_, assets) = extract_links(
            &html,
            &page_url,
            follow_re.as_ref(),
            &opts.extensions,
            None,
        );
        for asset in assets {
            to_download.push((page_url.clone(), asset));
        }
        followed.push(page_url);
    }

    let mut seen = std::collections::HashSet::new();
    let mut unique = Vec::new();
    for (page, asset) in to_download {
        if seen.insert(asset.clone()) {
            unique.push((page, asset));
        }
    }

    Ok((followed, unique))
}

pub async fn crawl_and_download(
    start_url: &str,
    out_dir: &Path,
    opts: &CrawlOptions,
) -> Result<(Vec<String>, Vec<String>, Vec<String>)> {
    let referer = Url::parse(start_url)
        .ok()
        .map(|u| format!("{}://{}/", u.scheme(), u.host_str().unwrap_or("")));
    let client = build_client(opts, referer.as_deref())?;

    let (followed, unique_downloads) = collect_pages_and_assets(start_url, opts).await?;
    let total = unique_downloads.len();
    let mut downloaded = Vec::new();
    let mut failed = Vec::new();

    for (idx, (page_url, asset_url)) in unique_downloads.into_iter().enumerate() {
        println!(
            "  [{}/{}] {}",
            idx + 1,
            total,
            filename_from_url(&asset_url)
        );
        let subdir = if opts.use_subdirs {
            subdir_from_page_url(&page_url)
        } else {
            String::new()
        };
        let name = filename_from_url(&asset_url);
        let ext = PathBuf::from(&name)
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| format!(".{e}"))
            .unwrap_or_default();
        let dest = if subdir.is_empty() {
            out_dir.join(&name)
        } else {
            out_dir.join(&subdir).join(&name)
        };
        match download_file(
            &client,
            &asset_url,
            &dest,
            opts.overwrite,
            if ext.is_empty() { None } else { Some(&ext) },
        )
        .await
        {
            Ok(true) => downloaded.push(asset_url),
            _ => failed.push(asset_url),
        }
        tokio::time::sleep(delay(opts.delay_sec)).await;
    }

    Ok((followed, downloaded, failed))
}

pub async fn list_asset_urls(start_url: &str, opts: &CrawlOptions) -> Result<Vec<String>> {
    let (_, pairs) = collect_pages_and_assets(start_url, opts).await?;
    Ok(pairs.into_iter().map(|(_, url)| url).collect())
}

fn delay(secs: f64) -> Duration {
    Duration::from_secs_f64(secs.max(0.0))
}
