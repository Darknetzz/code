use std::collections::HashMap;
use std::ffi::OsStr;
use std::fs;
use std::os::windows::ffi::OsStrExt;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use winreg::enums::*;
use winreg::RegKey;
use winreg::RegValue;

const HKCU_ENV: &str = r"Environment";
const HKLM_ENV: &str = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment";

/// Legacy payload (path-only); still accepted by `--apply-machine`.
#[derive(Debug, Serialize, Deserialize)]
pub struct MachinePathPayload {
    pub path: String,
}

#[derive(Debug, Serialize, Deserialize, Default)]
pub struct MachineApplyPayload {
    #[serde(default)]
    pub path: Option<String>,
    #[serde(default)]
    pub set: HashMap<String, String>,
    #[serde(default)]
    pub remove: Vec<String>,
}

pub fn read_user_path() -> Result<String> {
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let env = hkcu.open_subkey(HKCU_ENV).context("open HKCU Environment")?;
    let path: String = env.get_value("Path").unwrap_or_default();
    Ok(path)
}

pub fn read_machine_path() -> Result<String> {
    let hklm = RegKey::predef(HKEY_LOCAL_MACHINE);
    let env = hklm.open_subkey(HKLM_ENV).context("open HKLM Environment")?;
    let path: String = env.get_value("Path").unwrap_or_default();
    Ok(path)
}

pub fn read_user_env() -> Result<HashMap<String, String>> {
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let env = hkcu.open_subkey(HKCU_ENV).context("open HKCU Environment")?;
    read_registry_env_map(&env)
}

pub fn read_system_env() -> Result<HashMap<String, String>> {
    let hklm = RegKey::predef(HKEY_LOCAL_MACHINE);
    let env = hklm.open_subkey(HKLM_ENV).context("open HKLM Environment")?;
    read_registry_env_map(&env)
}

fn read_registry_env_map(env: &RegKey) -> Result<HashMap<String, String>> {
    let mut map = HashMap::new();
    for result in env.enum_values() {
        let (name, value) = result.map_err(|e| anyhow!("read registry value: {e}"))?;
        if crate::env_model::is_path_var(&name) {
            continue;
        }
        if let Ok(s) = reg_value_to_string(&value) {
            map.insert(name, s);
        }
    }
    Ok(map)
}

fn reg_value_to_string(value: &RegValue) -> Result<String> {
    match value.vtype {
        REG_SZ | REG_EXPAND_SZ => decode_utf16_null(&value.bytes),
        _ => Err(anyhow!("unsupported registry type for env var")),
    }
}

fn decode_utf16_null(bytes: &[u8]) -> Result<String> {
    if bytes.len() % 2 != 0 {
        return Err(anyhow!("invalid UTF-16 registry value"));
    }
    let mut units: Vec<u16> = bytes
        .chunks_exact(2)
        .map(|c| u16::from_le_bytes([c[0], c[1]]))
        .collect();
    while units.last() == Some(&0) {
        units.pop();
    }
    String::from_utf16(&units).context("registry value is not valid UTF-16")
}

fn encode_utf16_null(s: &str) -> Vec<u8> {
    let mut units: Vec<u16> = OsStr::new(s).encode_wide().collect();
    units.push(0);
    units.iter().flat_map(|u| u.to_le_bytes()).collect()
}

fn write_registry_value(env: &RegKey, name: &str, value: &str) -> Result<()> {
    let vtype = if value.contains('%') {
        REG_EXPAND_SZ
    } else {
        REG_SZ
    };
    env.set_raw_value(
        name,
        &RegValue {
            vtype,
            bytes: encode_utf16_null(value),
        },
    )
    .with_context(|| format!("set registry value {name}"))
}

pub fn write_user_path(new_path: &str) -> Result<()> {
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let (env, _) = hkcu
        .create_subkey(HKCU_ENV)
        .context("create HKCU Environment")?;
    env.set_value("Path", &new_path).context("set Path")?;
    drop(env);
    notify_setting_change()?;
    Ok(())
}

pub fn write_machine_path(new_path: &str) -> Result<()> {
    let hklm = RegKey::predef(HKEY_LOCAL_MACHINE);
    let env = hklm.open_subkey_with_flags(HKLM_ENV, KEY_WRITE)?;
    env.set_value("Path", &new_path).context("set machine Path")?;
    drop(env);
    notify_setting_change()?;
    Ok(())
}

pub fn write_user_env(vars: &HashMap<String, String>, remove: &[String]) -> Result<()> {
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let (env, _) = hkcu
        .create_subkey(HKCU_ENV)
        .context("create HKCU Environment")?;
    for name in remove {
        if crate::env_model::is_path_var(name) {
            continue;
        }
        let _ = env.delete_value(name);
    }
    for (name, value) in vars {
        if crate::env_model::is_path_var(name) {
            continue;
        }
        write_registry_value(&env, name, value)?;
    }
    drop(env);
    notify_setting_change()?;
    Ok(())
}

pub fn write_system_env(vars: &HashMap<String, String>, remove: &[String]) -> Result<()> {
    let hklm = RegKey::predef(HKEY_LOCAL_MACHINE);
    let env = hklm.open_subkey_with_flags(HKLM_ENV, KEY_WRITE)?;
    for name in remove {
        if crate::env_model::is_path_var(name) {
            continue;
        }
        let _ = env.delete_value(name);
    }
    for (name, value) in vars {
        if crate::env_model::is_path_var(name) {
            continue;
        }
        write_registry_value(&env, name, value)?;
    }
    drop(env);
    notify_setting_change()?;
    Ok(())
}

fn notify_setting_change() -> Result<()> {
    unsafe {
        use windows_sys::Win32::Foundation::{HWND, LPARAM, WPARAM};
        use windows_sys::Win32::UI::WindowsAndMessaging::{
            SendMessageTimeoutW, SMTO_ABORTIFHUNG, WM_SETTINGCHANGE,
        };
        let broadcast: HWND = 0xffff as HWND;
        let area: Vec<u16> = "Environment\0".encode_utf16().collect();
        let mut result: usize = 0;
        SendMessageTimeoutW(
            broadcast,
            WM_SETTINGCHANGE,
            0 as WPARAM,
            area.as_ptr() as LPARAM,
            SMTO_ABORTIFHUNG,
            5000,
            &mut result,
        );
    }
    Ok(())
}

pub fn backup_path(kind: &str, contents: &str, backup_dir: &Path) -> Result<PathBuf> {
    fs::create_dir_all(backup_dir)?;
    let ts = chrono::Local::now().format("%Y%m%d-%H%M%S");
    let name = format!("path-backup-{kind}-{ts}.txt");
    let p = backup_dir.join(name);
    fs::write(&p, contents)?;
    Ok(p)
}

pub fn backup_env_json(kind: &str, value: &HashMap<String, String>, backup_dir: &Path) -> Result<PathBuf> {
    fs::create_dir_all(backup_dir)?;
    let ts = chrono::Local::now().format("%Y%m%d-%H%M%S");
    let name = format!("env-backup-{kind}-{ts}.json");
    let p = backup_dir.join(name);
    let json = serde_json::to_string_pretty(value)?;
    fs::write(&p, json)?;
    Ok(p)
}

/// Write payload JSON and re-launch this exe elevated to apply machine PATH/env.
pub fn request_elevated_machine_apply(payload: MachineApplyPayload) -> Result<()> {
    let dir = std::env::temp_dir();
    let file = dir.join(format!("pathman-machine-{}.json", std::process::id()));
    let json = serde_json::to_string_pretty(&payload)?;
    fs::write(&file, &json)?;

    let exe = std::env::current_exe().context("current_exe")?;
    let exe_str = exe.to_string_lossy();
    let file_str = file.to_string_lossy();

    let ps = format!(
        "Start-Process -FilePath '{}' -ArgumentList '--apply-machine','{}' -Verb RunAs -Wait",
        escape_ps_single(&exe_str),
        escape_ps_single(&file_str)
    );
    let status = std::process::Command::new("powershell.exe")
        .args(["-NoProfile", "-WindowStyle", "Hidden", "-Command", &ps])
        .status()
        .context("spawn elevated PowerShell")?;
    let _ = fs::remove_file(&file);
    if !status.success() {
        return Err(anyhow!("elevated process exited with {:?}", status.code()));
    }
    Ok(())
}

/// Convenience wrapper for PATH-only machine saves.
pub fn request_elevated_machine_path(new_machine_path: &str) -> Result<()> {
    request_elevated_machine_apply(MachineApplyPayload {
        path: Some(new_machine_path.to_string()),
        ..Default::default()
    })
}

fn escape_ps_single(s: &str) -> String {
    s.replace('\'', "''")
}

/// Headless entry: apply machine PATH/env from JSON file (must run elevated).
pub fn apply_machine_from_file(path: &str) -> Result<()> {
    let json = fs::read_to_string(path).context("read payload")?;
    if let Ok(payload) = serde_json::from_str::<MachineApplyPayload>(&json) {
        apply_machine_payload(&payload)?;
        return Ok(());
    }
    let payload: MachinePathPayload = serde_json::from_str(&json).context("parse payload")?;
    write_machine_path(&payload.path)?;
    Ok(())
}

fn apply_machine_payload(payload: &MachineApplyPayload) -> Result<()> {
    if let Some(path) = &payload.path {
        write_machine_path(path)?;
    }
    if !payload.set.is_empty() || !payload.remove.is_empty() {
        let existing = read_system_env().unwrap_or_default();
        let mut merged = existing;
        for name in &payload.remove {
            merged.remove(name);
        }
        for (name, value) in &payload.set {
            merged.insert(name.clone(), value.clone());
        }
        write_system_env(&merged, &payload.remove)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn machine_apply_payload_roundtrip() {
        let payload = MachineApplyPayload {
            path: Some("C:\\bin".into()),
            set: HashMap::from([("MY_VAR".into(), "hello".into())]),
            remove: vec!["OLD".into()],
        };
        let json = serde_json::to_string(&payload).unwrap();
        let back: MachineApplyPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(back.path, payload.path);
        assert_eq!(back.set, payload.set);
        assert_eq!(back.remove, payload.remove);
    }

    #[test]
    fn legacy_path_payload_still_parses() {
        let json = r#"{"path":"C:\\x"}"#;
        let legacy: MachinePathPayload = serde_json::from_str(json).unwrap();
        assert_eq!(legacy.path, "C:\\x");
    }
}
