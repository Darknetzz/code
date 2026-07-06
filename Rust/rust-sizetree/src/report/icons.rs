use std::path::Path;

fn svg_icon(inner: &str, size: u32, class: &str) -> String {
    format!(
        r#"<svg viewBox="0 0 16 16" width="{size}" height="{size}" fill="currentColor" aria-hidden="true" class="{class}">{inner}</svg>"#
    )
}

fn icon_path(name: &str) -> Option<&'static str> {
    Some(match name {
        "dir" => "M1.75 1h3.5c.28 0 .54.11.73.28l1.5 1.47h6.77c.97 0 1.75.78 1.75 1.75v8.75c0 .97-.78 1.75-1.75 1.75H1.75A1.75 1.75 0 0 1 0 13.25V2.75C0 1.78.78 1 1.75 1Z",
        "file" => "M2 1.75C2 .78 2.78 0 3.75 0h6.5a.75.75 0 0 1 .53.22l4.25 4.25c.14.14.22.33.22.53v9.25A1.75 1.75 0 0 1 13.5 16h-9.75A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .14.11.25.25.25h9.75a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9.25 4.25V1.5Zm6.75.56v2.19c0 .14.11.25.25.25h2.19Z",
        "search" => "M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-1.06 1.06ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z",
        "label" => "M2.5 7.775V2.75a.25.25 0 0 1 .25-.25h5.025a.25.25 0 0 1 .177.073l6.25 6.25a.25.25 0 0 1 0 .354l-5.025 5.025a.25.25 0 0 1-.354 0l-6.25-6.25a.25.25 0 0 1-.073-.177Zm-1.5 0V2.75C1 1.784 1.784 1 2.75 1h5.025c.464 0 .91.184 1.238.513l6.25 6.25a1.75 1.75 0 0 1 0 2.474l-5.026 5.026a1.75 1.75 0 0 1-2.474 0l-6.25-6.25A1.748 1.748 0 0 1 1 7.775ZM6 5a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z",
        "pie" => "M8 0a8 8 0 1 1-3.2 15.33.75.75 0 1 1 .6-1.37A6.5 6.5 0 1 0 1.53 5.6a.75.75 0 1 1-1.36-.63A8 8 0 0 1 8 0Zm1.6 1.65A6.5 6.5 0 0 1 14.35 6.4.75.75 0 0 1 13.6 7.3H9.25a.75.75 0 0 1-.75-.75V2.2a.75.75 0 0 1 1.1-.55ZM10 3.76v1.74h1.74A5 5 0 0 0 10 3.76Z",
        "disk" => "M0 2.75C0 1.784.784 1 1.75 1h12.5c.966 0 1.75.784 1.75 1.75v3.5c0 .412-.144.79-.383 1.088.239.297.383.676.383 1.087v3.5A1.75 1.75 0 0 1 14.25 13.75H1.75A1.75 1.75 0 0 1 0 12v-3.5c0-.411.144-.79.383-1.087A1.742 1.742 0 0 1 0 6.25v-3.5Zm1.75-.25a.25.25 0 0 0-.25.25v3.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-3.5a.25.25 0 0 0-.25-.25H1.75ZM2.5 4.25a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5a.75.75 0 0 1-.75-.75Zm9.25-.75a.75.75 0 0 0 0 1.5h.5a.75.75 0 0 0 0-1.5h-.5ZM1.5 12c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-3.5a.25.25 0 0 0-.25-.25H1.75a.25.25 0 0 0-.25.25V12Zm1.75-1.75a.75.75 0 0 1 .75.75.75.75 0 0 1-.75.75.75.75 0 0 1-.75-.75.75.75 0 0 1 .75-.75Zm9 0a.75.75 0 0 0 0 1.5h.5a.75.75 0 0 0 0-1.5h-.5Z",
        "folder_up" => "M0 2.75C0 1.784.784 1 1.75 1h3.502c.464 0 .91.184 1.238.513L7.75 2.75h6.5c.966 0 1.75.784 1.75 1.75v8.75A1.75 1.75 0 0 1 14.25 15H1.75A1.75 1.75 0 0 1 0 13.25V2.75Zm8.53 6.53L7.25 8v3.75a.75.75 0 0 1-1.5 0V8L4.47 9.28a.75.75 0 0 1-1.06-1.06l2.5-2.5a.75.75 0 0 1 1.06 0l2.5 2.5a.75.75 0 1 1-1.06 1.06Z",
        "expand_all" => "M3.97 4.03a.75.75 0 0 1 1.06 0L8 7l2.97-2.97a.75.75 0 1 1 1.06 1.06L8.53 8.53a.75.75 0 0 1-1.06 0L3.97 5.09a.75.75 0 0 1 0-1.06Zm0 4a.75.75 0 0 1 1.06 0L8 11l2.97-2.97a.75.75 0 1 1 1.06 1.06l-3.5 3.5a.75.75 0 0 1-1.06 0L3.97 9.09a.75.75 0 0 1 0-1.06Z",
        "collapse_all" => "M3.97 8.03a.75.75 0 0 0 1.06 0L8 5.06l2.97 2.97a.75.75 0 0 0 1.06-1.06L8.53 3.47a.75.75 0 0 0-1.06 0L3.97 6.97a.75.75 0 0 0 0 1.06Zm0 4a.75.75 0 0 0 1.06 0L8 9.06l2.97 2.97a.75.75 0 0 0 1.06-1.06l-3.5-3.5a.75.75 0 0 0-1.06 0l-3.5 3.5a.75.75 0 0 0 0 1.06Z",
        "eye" => "M8 2c1.981 0 3.671.992 4.933 2.078 1.27 1.091 2.187 2.36 2.637 3.023a1.62 1.62 0 0 1 0 1.798c-.45.663-1.367 1.932-2.637 3.023C11.67 13.008 9.98 14 8 14c-1.981 0-3.671-.992-4.933-2.078C1.797 10.83.88 9.56.43 8.898a1.62 1.62 0 0 1 0-1.798c.45-.663 1.367-1.932 2.637-3.023C4.33 2.992 6.02 2 8 2Zm0 2.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7ZM8 9.5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3Z",
        "eye_slash" => "m.47 1.53 14 14a.75.75 0 1 0 1.06-1.06l-2.2-2.2c1.18-.9 2-1.94 2.45-2.59a1.62 1.62 0 0 0 0-1.79c-.45-.66-1.37-1.93-2.64-3.03C11.88 3.78 10.06 2.75 8 2.75c-1.36 0-2.58.46-3.63 1.08L1.53.47A.75.75 0 0 0 .47 1.53ZM8 11.25a3.25 3.25 0 0 1-3.18-3.94L3.56 6.05a16.3 16.3 0 0 0-1.48 1.8 1.62 1.62 0 0 0 0 1.79c.45.66 1.37 1.93 2.64 3.03C5.96 13.85 6.94 14 8 14c.85 0 1.66-.17 2.43-.46l-1.25-1.26a3.22 3.22 0 0 1-1.18.22ZM8 5.25c.45 0 .88.09 1.26.26L6.52 8.26a3.25 3.25 0 0 1 1.48-3.01Z",
        _ => return None,
    })
}

fn icon_extra(name: &str) -> Option<&'static str> {
    Some(match name {
        "file_code" => r#"<path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M5.5 5 2 8l3.5 3M10.5 5 14 8l-3.5 3M9.5 3.5l-3 9"/>"#,
        "file_image" => r#"<rect x="1.5" y="2.5" width="13" height="11" rx="1.25" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="5.5" cy="6" r="1.3"/><path d="M2.5 12.5l3.2-3.2 2 2 3.5-4 2.8 3.2v2H2.5z"/>"#,
        "file_video" => r#"<rect x="1.5" y="2.5" width="13" height="11" rx="1.25" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M6.5 5.2v5.6L11.3 8z"/>"#,
        "file_audio" => r#"<path d="M13.5 1 5.5 2.8V11a2.5 2.5 0 1 1-1.5-2.3V2L13.5 .2v8.3a2.5 2.5 0 1 1-1.5-2.3V1z"/>"#,
        "file_archive" => r#"<path fill-rule="evenodd" d="M2 3h12v12H2V3zm5 0h2v2H7V3zm0 3h2v2H7V6zm0 3h2v3H7V9z"/><path d="M1 1h14v2H1V1z"/>"#,
        "file_pdf" => r##"<path fill-rule="evenodd" d="M4 0h9a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zm0 1.5A.5.5 0 0 0 3.5 2v9.55A3 3 0 0 1 4 12h9V1.5H4zM4 13a1 1 0 1 0 0 2h9v-2H4z"/><path fill="#0d1117" d="M5 4.5h6.5v1H5v-1zm0 2h6.5v1H5v-1zm0 2h4.5v1H5v-1z"/>"##,
        "file_doc" => r#"<path fill-rule="evenodd" d="M3.75 0A1.75 1.75 0 0 0 2 1.75v12.5C2 15.22 2.78 16 3.75 16h9.75a1.75 1.75 0 0 0 1.75-1.75V5a.75.75 0 0 0-.22-.53L10.78.22A.75.75 0 0 0 10.25 0H3.75zM4.5 7.5h7v1h-7v-1zm0 2.5h7v1h-7v-1zm0 2.5h5v1h-5v-1z"/>"#,
        "file_text" => r#"<path fill-rule="evenodd" d="M3.75 0A1.75 1.75 0 0 0 2 1.75v12.5C2 15.22 2.78 16 3.75 16h9.75a1.75 1.75 0 0 0 1.75-1.75V5a.75.75 0 0 0-.22-.53L10.78.22A.75.75 0 0 0 10.25 0H3.75zM4.5 5.5h4v1h-4v-1zm0 2h7v1h-7v-1zm0 2.5h7v1h-7v-1zm0 2.5h5v1h-5v-1z"/>"#,
        "file_html" => r#"<circle cx="8" cy="8" r="6.75" fill="none" stroke="currentColor" stroke-width="1.4"/><ellipse cx="8" cy="8" rx="3.25" ry="6.75" fill="none" stroke="currentColor" stroke-width="1.4"/><line x1="1.25" y1="8" x2="14.75" y2="8" stroke="currentColor" stroke-width="1.4"/>"#,
        "file_config" => r#"<path d="M1 3.25A.75.75 0 0 1 1.75 2.5h4.5a.75.75 0 0 1 0 1.5h-4.5A.75.75 0 0 1 1 3.25zm9 0a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5A.75.75 0 0 1 10 3.25zM8 1.5a1.75 1.75 0 1 0 0 3.5 1.75 1.75 0 0 0 0-3.5zM1 8a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5A.75.75 0 0 1 1 8zm6 0a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5A.75.75 0 0 1 7 8zM5 6.25a1.75 1.75 0 1 0 0 3.5 1.75 1.75 0 0 0 0-3.5zM1 12.75a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5a.75.75 0 0 1-.75-.75zm11 0a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5a.75.75 0 0 1-.75-.75zM10 11a1.75 1.75 0 1 0 0 3.5 1.75 1.75 0 0 0 0-3.5z"/>"#,
        "file_exec" => r#"<rect x="0.75" y="1.75" width="14.5" height="12.5" rx="1.25" fill="none" stroke="currentColor" stroke-width="1.4"/><path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="M4 6l2.5 2L4 10M9 10.25h3"/>"#,
        "file_spreadsheet" => r#"<rect x="1.5" y="2.5" width="13" height="11" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M2.5 3.5h3.5v2H2.5V3.5zm4.5 0h3v2H7V3.5zm4 0h1.5v2H11V3.5zM2.5 7h3.5v2H2.5V7zm4.5 0h3v2H7V7zm4 0h1.5v2H11V7zM2.5 10.5h3.5v2H2.5v-2zm4.5 0h3v2H7v-2zm4 0h1.5v2H11v-2z"/>"#,
        _ => return None,
    })
}

pub fn icon(name: &str, size: u32, class: &str) -> String {
    let inner = icon_extra(name)
        .map(str::to_string)
        .or_else(|| icon_path(name).map(|d| format!(r#"<path d="{d}"/>"#)))
        .unwrap_or_else(|| format!(r#"<path d="{}"/>"#, icon_path("file").unwrap()));
    svg_icon(&inner, size, class)
}

pub fn btn_label(icon_name: &str, text: &str) -> String {
    format!(
        r#"<span class="btn-icon">{}</span>{}"#,
        icon(icon_name, 13, "chrome-icon"),
        text
    )
}

pub fn th_sort(key: &str, label: &str, icon_name: &str, extra_class: &str) -> String {
    let cls = if extra_class.is_empty() {
        "sortable".to_string()
    } else {
        format!("sortable {extra_class}")
    };
    format!(
        r#"<th class="{cls}" data-sort-key="{key}" scope="col"><span class="th-inner"><span class="th-icon">{}</span>{label}</span></th>"#,
        icon(icon_name, 12, "chrome-icon")
    )
}

fn ext_matches(ext: &str, list: &[&str]) -> bool {
    list.iter().any(|e| *e == ext)
}

pub fn file_icon_key(name: &str) -> &'static str {
    let lower = name.to_ascii_lowercase();
    match lower.as_str() {
        "dockerfile" | "containerfile" | "makefile" | "gnumakefile" | "cmakelists.txt"
        | "rakefile" | "vagrantfile" | "jenkinsfile" => return "file_code",
        "gemfile" | "gemfile.lock" | "procfile" => return "file_config",
        "readme" | "readme.md" | "readme.txt" | "license" | "license.txt" | "license.md"
        | "copying" | "changelog" | "authors" | "contributors" => return "file_text",
        _ => {}
    }
    if let Some(ext) = Path::new(&lower).extension().and_then(|e| e.to_str()) {
        if ext_matches(
            ext,
            &[
                "py", "pyw", "pyi", "pyx", "js", "mjs", "cjs", "jsx", "ts", "tsx", "c", "cc",
                "cpp", "cxx", "h", "hh", "hpp", "hxx", "rs", "go", "zig", "java", "kt", "cs",
                "rb", "php", "lua", "swift", "sh", "bash", "ps1", "bat", "cmd", "vue", "svelte",
                "css", "scss", "sass", "less",
            ],
        ) {
            return "file_code";
        }
        if ext_matches(ext, &["html", "htm", "xhtml", "xml", "xsl", "xslt"]) {
            return "file_html";
        }
        if ext_matches(
            ext,
            &[
                "json", "jsonc", "yaml", "yml", "toml", "ini", "cfg", "conf", "env", "sql",
                "sqlite", "lock",
            ],
        ) {
            return "file_config";
        }
        if ext_matches(
            ext,
            &[
                "png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "svg", "tif", "tiff", "heic",
                "avif", "psd",
            ],
        ) {
            return "file_image";
        }
        if ext_matches(
            ext,
            &["mp4", "m4v", "mov", "avi", "mkv", "webm", "wmv", "mpeg", "mpg"],
        ) {
            return "file_video";
        }
        if ext_matches(
            ext,
            &["mp3", "wav", "flac", "ogg", "m4a", "aac", "wma", "opus"],
        ) {
            return "file_audio";
        }
        if ext_matches(
            ext,
            &["zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "rar", "iso", "dmg"],
        ) {
            return "file_archive";
        }
        if ext == "pdf" {
            return "file_pdf";
        }
        if ext_matches(ext, &["doc", "docx", "odt", "rtf", "ppt", "pptx", "odp"]) {
            return "file_doc";
        }
        if ext_matches(ext, &["xls", "xlsx", "ods", "csv", "tsv"]) {
            return "file_spreadsheet";
        }
        if ext_matches(
            ext,
            &["txt", "text", "md", "markdown", "mdx", "rst", "log", "nfo"],
        ) {
            return "file_text";
        }
        if ext_matches(
            ext,
            &[
                "exe", "msi", "app", "deb", "rpm", "apk", "dll", "so", "dylib", "bin", "wasm",
                "pyc", "jar", "class",
            ],
        ) {
            return "file_exec";
        }
    }
    "file"
}
