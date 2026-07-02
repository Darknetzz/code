use std::path::Path;

use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(default)]
pub struct FileConfig {
    pub checks: Vec<CustomCheck>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CustomCheck {
    pub id: String,
    #[serde(default = "default_true")]
    pub required: bool,
    pub commands: Vec<String>,
    #[serde(default)]
    pub args: Vec<String>,
    pub hint: Option<String>,
}

fn default_true() -> bool {
    true
}

pub fn load_file_config(path: Option<&Path>) -> Result<FileConfig> {
    let Some(path) = path else {
        return Ok(FileConfig::default());
    };
    let raw = std::fs::read_to_string(path)
        .with_context(|| format!("Config file not found: {}", path.display()))?;
    serde_yaml::from_str(&raw)
        .with_context(|| format!("Failed to parse config: {}", path.display()))
}
