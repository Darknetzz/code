use std::path::Path;

fn ext_matches(ext: &str, list: &[&str]) -> bool {
    list.iter().any(|e| *e == ext)
}

/// Shared file-type key for HTML report icons and GUI Lucide icons.
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
