use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};

use crate::config::AppConfig;

pub const BEGIN_MARK: &str = "# --- pathman managed BEGIN ---";
pub const END_MARK: &str = "# --- pathman managed END ---";

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemPathPayload {
    /// macOS: lines for /etc/paths.d; Linux: colon-separated PATH prefix
    pub format: String,
    pub content: String,
}

fn backup_dir() -> Result<PathBuf> {
    let mut d = dirs::config_dir().context("config_dir")?;
    d.push("pathman");
    d.push("backups");
    Ok(d)
}

pub fn backup_string(kind: &str, contents: &str) -> Result<PathBuf> {
    let dir = backup_dir()?;
    fs::create_dir_all(&dir)?;
    let ts = chrono::Local::now().format("%Y%m%d-%H%M%S");
    let name = format!("path-backup-{kind}-{ts}.txt");
    let p = dir.join(name);
    fs::write(&p, contents)?;
    Ok(p)
}

/// Read user PATH entries from managed block in configured file.
pub fn read_user_entries(cfg: &AppConfig) -> Result<Vec<String>> {
    let path = cfg.resolved_user_shell_path();
    if !path.exists() {
        return Ok(Vec::new());
    }
    let text = fs::read_to_string(&path).context("read shell file")?;
    Ok(parse_block_export_path(&text).unwrap_or_default())
}

fn parse_block_export_path(text: &str) -> Option<Vec<String>> {
    let start = text.find(BEGIN_MARK)?;
    let end = text.find(END_MARK)?;
    if end <= start {
        return None;
    }
    let block = &text[start + BEGIN_MARK.len()..end];
    for line in block.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some(rest) = line.strip_prefix("export PATH=") {
            let rest = rest.trim();
            let quoted = rest
                .strip_prefix('"')
                .and_then(|s| s.strip_suffix('"'))
                .or_else(|| rest.strip_prefix('\'').and_then(|s| s.strip_suffix('\'')));
            let value = quoted.unwrap_or(rest);
            // PREFIX:$PATH or PREFIX:${PATH}
            let prefix = value
                .split_once(":$PATH")
                .or_else(|| value.split_once(":${PATH}"))
                .map(|(a, _)| a)
                .unwrap_or(value);
            return Some(crate::path_model::split(prefix));
        }
    }
    None
}

/// Write user PATH entries to managed block (creates file if missing).
pub fn write_user_entries(cfg: &AppConfig, entries: &[String]) -> Result<()> {
    let path = cfg.resolved_user_shell_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let joined = crate::path_model::join(entries);
    let export_line = format!("export PATH=\"{}:$PATH\"", escape_sh_double(&joined));

    let new_block = format!(
        "{BEGIN_MARK}\n{export_line}\n{END_MARK}\n",
        BEGIN_MARK = BEGIN_MARK,
        END_MARK = END_MARK,
        export_line = export_line
    );

    let text = if path.exists() {
        fs::read_to_string(&path)?
    } else {
        String::new()
    };

    let updated = if let Some(start) = text.find(BEGIN_MARK) {
        if let Some(end) = text.find(END_MARK) {
            let end_line = end + END_MARK.len();
            let after = text[end_line..].trim_start_matches('\n');
            format!(
                "{}{}{}",
                &text[..start],
                new_block.trim_end(),
                if after.is_empty() {
                    String::new()
                } else {
                    format!("\n{}", after)
                }
            )
        } else {
            format!("{}\n{}", text.trim_end(), new_block)
        }
    } else {
        if text.is_empty() {
            new_block
        } else {
            format!("{}\n{}", text.trim_end(), new_block)
        }
    };

    fs::write(&path, updated)?;
    Ok(())
}

fn escape_sh_double(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

/// Read system PATH entries for editing (platform-specific file).
pub fn read_system_entries() -> Result<Vec<String>> {
    #[cfg(target_os = "macos")]
    {
        let p = Path::new("/etc/paths.d/99-pathman");
        if !p.exists() {
            return Ok(Vec::new());
        }
        let s = fs::read_to_string(p).context("read paths.d")?;
        Ok(s.lines()
            .map(|l| l.trim().to_string())
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .collect())
    }
    #[cfg(not(target_os = "macos"))]
    {
        let p = Path::new("/etc/profile.d/pathman.sh");
        if !p.exists() {
            return Ok(Vec::new());
        }
        let s = fs::read_to_string(p).context("read profile.d")?;
        Ok(parse_block_export_path(&s).unwrap_or_default())
    }
}

pub fn write_system_entries(entries: &[String]) -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        let content = entries
            .iter()
            .map(|e| e.trim())
            .filter(|e| !e.is_empty())
            .collect::<Vec<_>>()
            .join("\n");
        if content.is_empty() {
            return Err(anyhow!(
                "refusing to write empty system PATH; remove entries via terminal if needed"
            ));
        }
        let tmp_data = std::env::temp_dir().join(format!("pathman-paths-{}", std::process::id()));
        fs::write(&tmp_data, format!("{}\n", content))?;
        let tmp_sh = std::env::temp_dir().join(format!("pathman-paths-sh-{}", std::process::id()));
        let data_q = sh_quote(&tmp_data);
        let sh_body = format!(
            "#!/bin/sh\nmkdir -p /etc/paths.d\n/usr/bin/install -m 644 {data_q} /etc/paths.d/99-pathman\n",
            data_q = data_q
        );
        fs::write(&tmp_sh, &sh_body)?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::metadata(&tmp_sh)?.permissions();
            perms.set_mode(0o700);
            fs::set_permissions(&tmp_sh, perms)?;
        }
        run_osascript_run_sh(&tmp_sh)?;
        let _ = fs::remove_file(&tmp_data);
        let _ = fs::remove_file(&tmp_sh);
        Ok(())
    }
    #[cfg(not(target_os = "macos"))]
    {
        let joined = crate::path_model::join(entries);
        if joined.is_empty() {
            return Err(anyhow!(
                "refusing to write empty system PATH; remove file via terminal if needed"
            ));
        }
        let body = format!(
            "# pathman managed — do not edit by hand\n\
             {BEGIN}\n\
             export PATH=\"{j}:$PATH\"\n\
             {END}\n",
            BEGIN = BEGIN_MARK,
            END = END_MARK,
            j = escape_sh_double(&joined)
        );
        let tmp = std::env::temp_dir().join(format!("pathman-profile-{}", std::process::id()));
        fs::write(&tmp, &body)?;
        try_pkexec_copy(&tmp, Path::new("/etc/profile.d/pathman.sh"))?;
        let _ = fs::remove_file(&tmp);
        Ok(())
    }
}

fn sh_quote(p: &Path) -> String {
    let s = p.to_string_lossy();
    format!("'{}'", s.replace('\'', "'\\''"))
}

fn applescript_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

/// Run a shell script file with admin privileges (macOS).
fn run_osascript_run_sh(script_path: &Path) -> Result<()> {
    let shell_cmd = format!("/bin/sh {}", sh_quote(script_path));
    let apple = format!(
        "do shell script \"{}\" with administrator privileges",
        applescript_escape(&shell_cmd)
    );
    let st = Command::new("osascript")
        .args(["-e", &apple])
        .status()
        .context("osascript")?;
    if !st.success() {
        return Err(anyhow!("osascript / admin denied ({:?})", st.code()));
    }
    Ok(())
}

fn try_pkexec_copy(src: &Path, dst: &Path) -> Result<()> {
    let src_q = sh_quote(src);
    let dst_q = sh_quote(dst);
    let shell = format!(
        "mkdir -p /etc/profile.d && /usr/bin/install -m 644 {src_q} {dst_q}",
        src_q = src_q,
        dst_q = dst_q
    );
    let st = Command::new("pkexec")
        .args(["/bin/sh", "-c", &shell])
        .status();
    match st {
        Ok(s) if s.success() => return Ok(()),
        Ok(s) => {
            return Err(anyhow!(
                "pkexec failed ({:?}). Try: sudo install -m 644 {} {}",
                s.code(),
                src_q,
                dst_q
            ));
        }
        Err(_) => {
            return Err(anyhow!(
                "pkexec not found. Run: sudo install -m 644 {} {}",
                src_q,
                dst_q
            ));
        }
    }
}

/// Headless: apply system payload (Linux profile.d body written via pkexec).
pub fn apply_system_from_file(path: &str) -> Result<()> {
    let json = fs::read_to_string(path).context("read payload")?;
    let payload: SystemPathPayload = serde_json::from_str(&json).context("parse payload")?;
    match payload.format.as_str() {
        "linux_profile" => {
            let tmp = std::env::temp_dir().join(format!("pathman-apply-{}", std::process::id()));
            fs::write(&tmp, &payload.content)?;
            try_pkexec_copy(&tmp, Path::new("/etc/profile.d/pathman.sh"))?;
            let _ = fs::remove_file(&tmp);
            Ok(())
        }
        "macos_paths_d" => {
            let tmp_data = std::env::temp_dir().join(format!("pathman-apply-{}", std::process::id()));
            fs::write(&tmp_data, &payload.content)?;
            let tmp_sh =
                std::env::temp_dir().join(format!("pathman-apply-sh-{}", std::process::id()));
            let data_q = sh_quote(&tmp_data);
            let sh_body = format!(
                "#!/bin/sh\nmkdir -p /etc/paths.d\n/usr/bin/install -m 644 {data_q} /etc/paths.d/99-pathman\n",
                data_q = data_q
            );
            fs::write(&tmp_sh, &sh_body)?;
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let mut perms = fs::metadata(&tmp_sh)?.permissions();
                perms.set_mode(0o700);
                fs::set_permissions(&tmp_sh, perms)?;
            }
            run_osascript_run_sh(&tmp_sh)?;
            let _ = fs::remove_file(&tmp_data);
            let _ = fs::remove_file(&tmp_sh);
            Ok(())
        }
        _ => Err(anyhow!("unknown payload format")),
    }
}
