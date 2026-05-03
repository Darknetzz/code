use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use winreg::enums::*;
use winreg::RegKey;

const HKCU_ENV: &str = r"Environment";
const HKLM_ENV: &str = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment";

#[derive(Debug, Serialize, Deserialize)]
pub struct MachinePathPayload {
    pub path: String,
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

/// Machine first, then user — typical effective PATH for new processes.
pub fn merged_preview() -> Result<String> {
    let m = read_machine_path().unwrap_or_default();
    let u = read_user_path().unwrap_or_default();
    let machine = crate::path_model::split(&m);
    let user = crate::path_model::split(&u);
    Ok(crate::path_model::join_merged_preview_style(&machine, &user))
}

pub fn write_user_path(new_path: &str) -> Result<()> {
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let (env, _) = hkcu.create_subkey(HKCU_ENV).context("create HKCU Environment")?;
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

/// Write payload JSON and re-launch this exe elevated to apply machine PATH.
pub fn request_elevated_machine_apply(new_machine_path: &str) -> Result<()> {
    let payload = MachinePathPayload {
        path: new_machine_path.to_string(),
    };
    let dir = std::env::temp_dir();
    let file = dir.join(format!(
        "pathman-machine-{}.json",
        std::process::id()
    ));
    let json = serde_json::to_string_pretty(&payload)?;
    fs::write(&file, &json)?;

    let exe = std::env::current_exe().context("current_exe")?;
    let exe_str = exe.to_string_lossy();
    let file_str = file.to_string_lossy();

    // Start-Process -Verb RunAs for UAC
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

fn escape_ps_single(s: &str) -> String {
    s.replace('\'', "''")
}

/// Headless entry: apply machine PATH from JSON file (must run elevated).
pub fn apply_machine_from_file(path: &str) -> Result<()> {
    let json = fs::read_to_string(path).context("read payload")?;
    let payload: MachinePathPayload = serde_json::from_str(&json).context("parse payload")?;
    write_machine_path(&payload.path)?;
    Ok(())
}
