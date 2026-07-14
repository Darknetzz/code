//! Platform-specific PATH and environment persistence.

#[cfg(windows)]
mod windows;
#[cfg(not(windows))]
mod unix;

#[cfg(windows)]
pub use windows::{
    apply_machine_from_file, backup_env_json, backup_path, read_machine_path, read_user_path,
    request_elevated_machine_apply, request_elevated_machine_path, write_user_path,
    MachineApplyPayload,
};

#[cfg(not(windows))]
pub use unix::{
    apply_system_from_file, backup_env_json, backup_string, read_system_entries, read_user_entries,
    write_system_entries, write_user_entries, BEGIN_MARK, END_MARK, ManagedBlock, SystemApplyPayload,
    SystemEnvPayload, SystemPathPayload,
};

use std::collections::HashMap;

use crate::config::AppConfig;

pub fn read_user_env(cfg: &AppConfig) -> anyhow::Result<HashMap<String, String>> {
    #[cfg(windows)]
    {
        let _ = cfg;
        windows::read_user_env()
    }
    #[cfg(not(windows))]
    {
        unix::read_user_env(cfg)
    }
}

pub fn read_system_env() -> anyhow::Result<HashMap<String, String>> {
    #[cfg(windows)]
    {
        windows::read_system_env()
    }
    #[cfg(not(windows))]
    {
        unix::read_system_env()
    }
}

pub fn write_user_env(
    cfg: &AppConfig,
    vars: &HashMap<String, String>,
    remove: &[String],
) -> anyhow::Result<()> {
    #[cfg(windows)]
    {
        let _ = cfg;
        windows::write_user_env(vars, remove)
    }
    #[cfg(not(windows))]
    {
        unix::write_user_env(cfg, vars, remove)
    }
}

#[cfg(not(windows))]
pub fn write_system_env(
    vars: &HashMap<String, String>,
    remove: &[String],
) -> anyhow::Result<()> {
    #[cfg(windows)]
    {
        windows::write_system_env(vars, remove)
    }
    #[cfg(not(windows))]
    {
        unix::write_system_env(vars, remove)
    }
}
