//! Merge/split/diff for non-PATH environment variables.

use std::collections::{HashMap, HashSet};

use crate::path_model::PathOrigin;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EnvEntry {
    pub name: String,
    pub value: String,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct EnvDiff {
    pub added: HashMap<String, String>,
    pub changed: HashMap<String, String>,
    pub removed: Vec<String>,
}

/// True when the name refers to PATH (edited in the PATH tab).
pub fn is_path_var(name: &str) -> bool {
    name.eq_ignore_ascii_case("path")
}

/// Validate a variable name for the Environment tab.
pub fn validate_var_name(name: &str) -> Result<(), String> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err("Variable name cannot be empty".into());
    }
    if is_path_var(trimmed) {
        return Err("PATH is edited in the PATH tab".into());
    }
    #[cfg(windows)]
    {
        let mut chars = trimmed.chars();
        let Some(first) = chars.next() else {
            return Err("Variable name cannot be empty".into());
        };
        if !first.is_ascii_alphabetic() && first != '_' {
            return Err("Name must start with a letter or underscore".into());
        }
        if !chars.all(|c| c.is_ascii_alphanumeric() || c == '_') {
            return Err("Name may only contain letters, digits, and underscores".into());
        }
    }
    Ok(())
}

/// Machine entries first; user overrides on name collision (Windows session merge for non-PATH).
pub fn merge_machine_user_env(
    machine: &HashMap<String, String>,
    user: &HashMap<String, String>,
) -> Vec<(PathOrigin, EnvEntry)> {
    let mut out = Vec::new();
    for (name, value) in machine {
        if is_path_var(name) {
            continue;
        }
        if user.contains_key(name) {
            continue;
        }
        out.push((
            PathOrigin::Machine,
            EnvEntry {
                name: name.clone(),
                value: value.clone(),
            },
        ));
    }
    for (name, value) in user {
        if is_path_var(name) {
            continue;
        }
        out.push((
            PathOrigin::User,
            EnvEntry {
                name: name.clone(),
                value: value.clone(),
            },
        ));
    }
    out.sort_by(|a, b| a.1.name.to_lowercase().cmp(&b.1.name.to_lowercase()));
    out
}

/// Split Effective-tab segments back into machine and user maps.
pub fn split_origins_env(segments: &[(PathOrigin, EnvEntry)]) -> (HashMap<String, String>, HashMap<String, String>) {
    let mut machine = HashMap::new();
    let mut user = HashMap::new();
    for (origin, entry) in segments {
        let name = entry.name.trim();
        if name.is_empty() || is_path_var(name) {
            continue;
        }
        match origin {
            PathOrigin::Machine => {
                machine.insert(name.to_string(), entry.value.clone());
            }
            PathOrigin::User => {
                user.insert(name.to_string(), entry.value.clone());
            }
        }
    }
    (machine, user)
}

/// Diff pending map against a baseline (for User/System scope saves).
pub fn diff_env(baseline: &HashMap<String, String>, pending: &HashMap<String, String>) -> EnvDiff {
    let mut added = HashMap::new();
    let mut changed = HashMap::new();
    let mut removed = Vec::new();

    for (name, value) in pending {
        match baseline.get(name) {
            None => {
                added.insert(name.clone(), value.clone());
            }
            Some(old) if old != value => {
                changed.insert(name.clone(), value.clone());
            }
            _ => {}
        }
    }
    for name in baseline.keys() {
        if !pending.contains_key(name) {
            removed.push(name.clone());
        }
    }
    removed.sort();

    EnvDiff {
        added,
        changed,
        removed,
    }
}

/// Collect names present in both machine and user stores (for duplicate hints).
pub fn cross_origin_env_names(
    machine: &HashMap<String, String>,
    user: &HashMap<String, String>,
) -> HashSet<String> {
    machine
        .keys()
        .filter(|k| !is_path_var(k) && user.contains_key(*k))
        .cloned()
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn map(pairs: &[(&str, &str)]) -> HashMap<String, String> {
        pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect()
    }

    #[test]
    fn merge_user_wins_collision() {
        let m = map(&[("A", "1"), ("B", "2")]);
        let u = map(&[("B", "u"), ("C", "3")]);
        let merged = merge_machine_user_env(&m, &u);
        let names: Vec<_> = merged
            .iter()
            .map(|(o, e)| (format!("{o:?}"), e.name.clone(), e.value.clone()))
            .collect();
        assert_eq!(names.len(), 3);
        assert!(merged.iter().any(|(o, e)| *o == PathOrigin::Machine && e.name == "A"));
        assert!(merged.iter().any(|(o, e)| *o == PathOrigin::User && e.name == "B" && e.value == "u"));
        assert!(merged.iter().any(|(o, e)| *o == PathOrigin::User && e.name == "C"));
        assert!(!merged.iter().any(|(o, e)| *o == PathOrigin::Machine && e.name == "B"));
    }

    #[test]
    fn split_origins_roundtrip() {
        let m = map(&[("X", "1")]);
        let u = map(&[("Y", "2")]);
        let merged = merge_machine_user_env(&m, &u);
        let (pm, pu) = split_origins_env(&merged);
        assert_eq!(pm.get("X").map(String::as_str), Some("1"));
        assert_eq!(pu.get("Y").map(String::as_str), Some("2"));
    }

    #[test]
    fn diff_detects_changes() {
        let base = map(&[("A", "1"), ("B", "2")]);
        let pending = map(&[("A", "1"), ("B", "3"), ("C", "4")]);
        let d = diff_env(&base, &pending);
        assert_eq!(d.added.get("C").map(String::as_str), Some("4"));
        assert_eq!(d.changed.get("B").map(String::as_str), Some("3"));
        assert!(d.removed.is_empty());
    }

    #[test]
    fn diff_detects_removals() {
        let base = map(&[("A", "1"), ("B", "2")]);
        let pending = map(&[("A", "1")]);
        let d = diff_env(&base, &pending);
        assert_eq!(d.removed, vec!["B".to_string()]);
    }

    #[test]
    fn path_var_forbidden() {
        assert!(validate_var_name("PATH").is_err());
        assert!(validate_var_name("Path").is_err());
        assert!(validate_var_name("MY_VAR").is_ok());
    }

    #[test]
    fn cross_origin_names() {
        let m = map(&[("A", "1"), ("B", "2")]);
        let u = map(&[("B", "x"), ("C", "3")]);
        let cross = cross_origin_env_names(&m, &u);
        assert_eq!(cross.len(), 1);
        assert!(cross.contains("B"));
    }
}
