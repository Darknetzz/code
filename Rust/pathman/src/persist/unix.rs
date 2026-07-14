use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};

use crate::config::AppConfig;
use crate::env_model::is_path_var;

pub const BEGIN_MARK: &str = "# --- pathman managed BEGIN ---";
pub const END_MARK: &str = "# --- pathman managed END ---";

const SYSTEM_ENV_FILE_MACOS: &str = "/etc/profile.d/99-pathman-env";
const SYSTEM_PATH_FILE_LINUX: &str = "/etc/profile.d/pathman.sh";

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ManagedBlock {
    pub path_prefix: Option<Vec<String>>,
    pub env: HashMap<String, String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemPathPayload {
    /// macOS: lines for /etc/paths.d; Linux: colon-separated PATH prefix
    pub format: String,
    pub content: String,
}

#[derive(Debug, Serialize, Deserialize, Default)]
pub struct SystemEnvPayload {
    pub format: String,
    pub content: String,
}

#[derive(Debug, Serialize, Deserialize, Default)]
pub struct SystemApplyPayload {
    #[serde(default)]
    pub path: Option<SystemPathPayload>,
    #[serde(default)]
    pub env: Option<SystemEnvPayload>,
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

pub fn backup_env_json(kind: &str, contents: &str) -> Result<PathBuf> {
    let dir = backup_dir()?;
    fs::create_dir_all(&dir)?;
    let ts = chrono::Local::now().format("%Y%m%d-%H%M%S");
    let name = format!("env-backup-{kind}-{ts}.json");
    let p = dir.join(name);
    fs::write(&p, contents)?;
    Ok(p)
}

pub fn parse_managed_block(text: &str) -> Option<ManagedBlock> {
    let start = text.find(BEGIN_MARK)?;
    let end = text.find(END_MARK)?;
    if end <= start {
        return None;
    }
    let block = &text[start + BEGIN_MARK.len()..end];
    let mut managed = ManagedBlock::default();
    for line in block.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some(rest) = line.strip_prefix("export PATH=") {
            managed.path_prefix = Some(parse_path_export_value(rest.trim()));
            continue;
        }
        if let Some((name, value)) = parse_export_line(line) {
            if !is_path_var(&name) {
                managed.env.insert(name, value);
            }
        }
    }
    Some(managed)
}

fn parse_path_export_value(rest: &str) -> Vec<String> {
    let quoted = rest
        .strip_prefix('"')
        .and_then(|s| s.strip_suffix('"'))
        .or_else(|| rest.strip_prefix('\'').and_then(|s| s.strip_suffix('\'')));
    let value = quoted.unwrap_or(rest);
    let prefix = value
        .split_once(":$PATH")
        .or_else(|| value.split_once(":${PATH}"))
        .map(|(a, _)| a)
        .unwrap_or(value);
    crate::path_model::split(prefix)
}

fn parse_export_line(line: &str) -> Option<(String, String)> {
    let rest = line.strip_prefix("export ")?;
    let (name, value_part) = rest.split_once('=')?;
    let name = name.trim();
    if name.is_empty() {
        return None;
    }
    let value_part = value_part.trim();
    let quoted = value_part
        .strip_prefix('"')
        .and_then(|s| s.strip_suffix('"'))
        .or_else(|| value_part.strip_prefix('\'').and_then(|s| s.strip_suffix('\'')));
    Some((name.to_string(), quoted.unwrap_or(value_part).to_string()))
}

pub fn render_managed_block(block: &ManagedBlock) -> String {
    let mut lines = vec![BEGIN_MARK.to_string()];
    if let Some(prefix) = &block.path_prefix {
        let joined = crate::path_model::join(prefix);
        lines.push(format!(
            "export PATH=\"{}:$PATH\"",
            escape_sh_double(&joined)
        ));
    }
    let mut names: Vec<_> = block.env.keys().collect();
    names.sort_by(|a, b| a.to_lowercase().cmp(&b.to_lowercase()));
    for name in names {
        let value = &block.env[name];
        lines.push(format!(
            "export {}=\"{}\"",
            name,
            escape_sh_double(value)
        ));
    }
    lines.push(END_MARK.to_string());
    format!("{}\n", lines.join("\n"))
}

fn read_user_file_text(cfg: &AppConfig) -> Result<String> {
    let path = cfg.resolved_user_shell_path();
    if !path.exists() {
        return Ok(String::new());
    }
    fs::read_to_string(&path).context("read shell file")
}

fn read_user_managed_block(cfg: &AppConfig) -> ManagedBlock {
    read_user_file_text(cfg)
        .ok()
        .and_then(|text| parse_managed_block(&text))
        .unwrap_or_default()
}

fn write_managed_block_to_user_file(cfg: &AppConfig, block: &ManagedBlock) -> Result<()> {
    let path = cfg.resolved_user_shell_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let new_block = render_managed_block(block);
    let text = read_user_file_text(cfg).unwrap_or_default();
    let updated = splice_managed_block(&text, &new_block);
    fs::write(&path, updated)?;
    Ok(())
}

fn splice_managed_block(text: &str, new_block: &str) -> String {
    if let Some(start) = text.find(BEGIN_MARK) {
        if let Some(end) = text.find(END_MARK) {
            let end_line = end + END_MARK.len();
            let after = text[end_line..].trim_start_matches('\n');
            return format!(
                "{}{}{}",
                &text[..start],
                new_block.trim_end(),
                if after.is_empty() {
                    String::new()
                } else {
                    format!("\n{}", after)
                }
            );
        }
        format!("{}\n{}", text.trim_end(), new_block)
    } else if text.is_empty() {
        new_block.to_string()
    } else {
        format!("{}\n{}", text.trim_end(), new_block)
    }
}

/// Read user PATH entries from managed block in configured file.
pub fn read_user_entries(cfg: &AppConfig) -> Result<Vec<String>> {
    Ok(read_user_managed_block(cfg)
        .path_prefix
        .unwrap_or_default())
}

/// Write user PATH entries to managed block (creates file if missing).
pub fn write_user_entries(cfg: &AppConfig, entries: &[String]) -> Result<()> {
    let mut block = read_user_managed_block(cfg);
    block.path_prefix = Some(entries.to_vec());
    write_managed_block_to_user_file(cfg, &block)
}

pub fn read_user_env(cfg: &AppConfig) -> Result<HashMap<String, String>> {
    Ok(read_user_managed_block(cfg).env)
}

pub fn write_user_env(
    cfg: &AppConfig,
    vars: &HashMap<String, String>,
    _remove: &[String],
) -> Result<()> {
    let mut block = read_user_managed_block(cfg);
    block.env = vars
        .iter()
        .filter(|(k, _)| !is_path_var(k))
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    write_managed_block_to_user_file(cfg, &block)
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
        Ok(s
            .lines()
            .map(|l| l.trim().to_string())
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .collect())
    }
    #[cfg(not(target_os = "macos"))]
    {
        let p = Path::new(SYSTEM_PATH_FILE_LINUX);
        if !p.exists() {
            return Ok(Vec::new());
        }
        let s = fs::read_to_string(p).context("read profile.d")?;
        Ok(parse_managed_block(&s)
            .and_then(|b| b.path_prefix)
            .unwrap_or_default())
    }
}

pub fn read_system_env() -> Result<HashMap<String, String>> {
    #[cfg(target_os = "macos")]
    {
        let p = Path::new(SYSTEM_ENV_FILE_MACOS);
        if !p.exists() {
            return Ok(HashMap::new());
        }
        let s = fs::read_to_string(p).context("read system env file")?;
        Ok(parse_managed_block(&s)
            .map(|b| b.env)
            .unwrap_or_default())
    }
    #[cfg(not(target_os = "macos"))]
    {
        let p = Path::new(SYSTEM_PATH_FILE_LINUX);
        if !p.exists() {
            return Ok(HashMap::new());
        }
        let s = fs::read_to_string(p).context("read profile.d")?;
        Ok(parse_managed_block(&s)
            .map(|b| b.env)
            .unwrap_or_default())
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
        fs::write(&tmp_data, format!("{content}\n"))?;
        install_macos_paths_d(&tmp_data)?;
        let _ = fs::remove_file(&tmp_data);
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
        let mut block = fs::read_to_string(Path::new(SYSTEM_PATH_FILE_LINUX))
            .ok()
            .and_then(|s| parse_managed_block(&s))
            .unwrap_or_default();
        block.path_prefix = Some(entries.to_vec());
        let body = format!(
            "# pathman managed — do not edit by hand\n{}",
            render_managed_block(&block)
        );
        let tmp = std::env::temp_dir().join(format!("pathman-profile-{}", std::process::id()));
        fs::write(&tmp, &body)?;
        try_pkexec_copy(&tmp, Path::new(SYSTEM_PATH_FILE_LINUX))?;
        let _ = fs::remove_file(&tmp);
        Ok(())
    }
}

pub fn write_system_env(vars: &HashMap<String, String>, _remove: &[String]) -> Result<()> {
    let filtered: HashMap<String, String> = vars
        .iter()
        .filter(|(k, _)| !is_path_var(k))
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    if filtered.is_empty() {
        return Err(anyhow!(
            "refusing to write empty system environment file; remove via terminal if needed"
        ));
    }

    #[cfg(target_os = "macos")]
    {
        let block = ManagedBlock {
            path_prefix: None,
            env: filtered,
        };
        let body = format!(
            "# pathman managed — do not edit by hand\n{}",
            render_managed_block(&block)
        );
        let tmp = std::env::temp_dir().join(format!("pathman-sysenv-{}", std::process::id()));
        fs::write(&tmp, &body)?;
        try_pkexec_copy(&tmp, Path::new(SYSTEM_ENV_FILE_MACOS))?;
        let _ = fs::remove_file(&tmp);
        Ok(())
    }
    #[cfg(not(target_os = "macos"))]
    {
        let mut block = fs::read_to_string(Path::new(SYSTEM_PATH_FILE_LINUX))
            .ok()
            .and_then(|s| parse_managed_block(&s))
            .unwrap_or_default();
        block.env = filtered;
        if block.path_prefix.is_none() && block.env.is_empty() {
            return Err(anyhow!("refusing to write empty system environment"));
        }
        let body = format!(
            "# pathman managed — do not edit by hand\n{}",
            render_managed_block(&block)
        );
        let tmp = std::env::temp_dir().join(format!("pathman-sysenv-{}", std::process::id()));
        fs::write(&tmp, &body)?;
        try_pkexec_copy(&tmp, Path::new(SYSTEM_PATH_FILE_LINUX))?;
        let _ = fs::remove_file(&tmp);
        Ok(())
    }
}

#[cfg(target_os = "macos")]
fn install_macos_paths_d(tmp_data: &Path) -> Result<()> {
    let tmp_sh = std::env::temp_dir().join(format!("pathman-paths-sh-{}", std::process::id()));
    let data_q = sh_quote(tmp_data);
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
    let _ = fs::remove_file(&tmp_sh);
    Ok(())
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
    let parent = dst.parent().unwrap_or(Path::new("/etc/profile.d"));
    let parent_q = sh_quote(parent);
    let shell = format!(
        "mkdir -p {parent_q} && /usr/bin/install -m 644 {src_q} {dst_q}",
        parent_q = parent_q,
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
    if let Ok(payload) = serde_json::from_str::<SystemApplyPayload>(&json) {
        if let Some(path_payload) = payload.path {
            apply_system_path_payload(&path_payload)?;
        }
        if let Some(env_payload) = payload.env {
            apply_system_env_payload(&env_payload)?;
        }
        return Ok(());
    }
    let payload: SystemPathPayload = serde_json::from_str(&json).context("parse payload")?;
    apply_system_path_payload(&payload)
}

fn apply_system_path_payload(payload: &SystemPathPayload) -> Result<()> {
    match payload.format.as_str() {
        "linux_profile" => {
            let tmp = std::env::temp_dir().join(format!("pathman-apply-{}", std::process::id()));
            fs::write(&tmp, &payload.content)?;
            try_pkexec_copy(&tmp, Path::new(SYSTEM_PATH_FILE_LINUX))?;
            let _ = fs::remove_file(&tmp);
            Ok(())
        }
        "macos_paths_d" => {
            let tmp_data = std::env::temp_dir().join(format!("pathman-apply-{}", std::process::id()));
            fs::write(&tmp_data, &payload.content)?;
            install_macos_paths_d(&tmp_data)?;
            let _ = fs::remove_file(&tmp_data);
            Ok(())
        }
        _ => Err(anyhow!("unknown path payload format")),
    }
}

fn apply_system_env_payload(payload: &SystemEnvPayload) -> Result<()> {
    match payload.format.as_str() {
        "linux_profile" | "macos_profile_d" => {
            let dst = if payload.format == "macos_profile_d" {
                Path::new(SYSTEM_ENV_FILE_MACOS)
            } else {
                Path::new(SYSTEM_PATH_FILE_LINUX)
            };
            let tmp = std::env::temp_dir().join(format!("pathman-apply-env-{}", std::process::id()));
            fs::write(&tmp, &payload.content)?;
            try_pkexec_copy(&tmp, dst)?;
            let _ = fs::remove_file(&tmp);
            Ok(())
        }
        _ => Err(anyhow!("unknown env payload format")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_render_roundtrip_with_path_and_env() {
        let block = ManagedBlock {
            path_prefix: Some(vec!["/a".into(), "/b".into()]),
            env: HashMap::from([
                ("MY_VAR".into(), "hello".into()),
                ("OTHER".into(), "world".into()),
            ]),
        };
        let rendered = render_managed_block(&block);
        let parsed = parse_managed_block(&rendered).expect("parse");
        assert_eq!(parsed.path_prefix, block.path_prefix);
        assert_eq!(parsed.env, block.env);
    }

    #[test]
    fn parse_export_lines_only_env() {
        let text = format!(
            "{BEGIN}\nexport FOO=\"bar\"\nexport BAZ='qux'\n{END}\n",
            BEGIN = BEGIN_MARK,
            END = END_MARK
        );
        let parsed = parse_managed_block(&text).expect("parse");
        assert_eq!(parsed.env.get("FOO").map(String::as_str), Some("bar"));
        assert_eq!(parsed.env.get("BAZ").map(String::as_str), Some("qux"));
        assert!(parsed.path_prefix.is_none());
    }
}
