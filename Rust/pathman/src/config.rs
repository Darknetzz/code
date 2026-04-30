//! XDG / user config: `pathman.toml` for Unix target file path.

use std::path::PathBuf;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

const FILE_NAME: &str = "pathman.toml";

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AppConfig {
    /// Absolute or home-relative path to the shell file we manage (Unix user scope).
    #[serde(default)]
    pub user_shell_path: Option<String>,
}

impl AppConfig {
    pub fn config_path() -> Result<PathBuf> {
        let dir = dirs::config_dir().context("no config dir")?;
        Ok(dir.join("pathman").join(FILE_NAME))
    }

    pub fn load() -> Self {
        Self::load_from_disk().unwrap_or_default()
    }

    fn load_from_disk() -> Result<Self> {
        let p = Self::config_path()?;
        if !p.exists() {
            return Ok(Self::default());
        }
        let s = std::fs::read_to_string(&p)?;
        Ok(toml::from_str(&s)?)
    }

    pub fn save(&self) -> Result<()> {
        let p = Self::config_path()?;
        if let Some(parent) = p.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let s = toml::to_string_pretty(self)?;
        std::fs::write(&p, s)?;
        Ok(())
    }

    /// Resolved path for Unix user PATH block file.
    pub fn resolved_user_shell_path(&self) -> PathBuf {
        if let Some(ref u) = self.user_shell_path {
            expand_home(u)
        } else {
            default_user_shell_path()
        }
    }
}

fn default_user_shell_path() -> PathBuf {
    if let Some(mut d) = dirs::config_dir() {
        d.push("pathman");
        d.push("path.sh");
        return d;
    }
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".config/pathman/path.sh")
}

fn expand_home(s: &str) -> PathBuf {
    if let Some(rest) = s.strip_prefix("~/") {
        return dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(rest);
    }
    if s == "~" {
        return dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
    }
    PathBuf::from(s)
}
