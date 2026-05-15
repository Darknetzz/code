#![allow(dead_code)]

use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

use crate::ast::Stmt;

#[derive(Clone)]
pub struct ShellState {
    pub env: HashMap<String, String>,
    pub cwd: PathBuf,
    pub last_status: i32,
    pub functions: HashMap<String, Vec<Stmt>>,
    pub positional: Vec<String>,
    pub argv0: String,
    /// When a builtin requests `exit`, REPL / main checks this.
    pub pending_exit: Option<i32>,
    exported: HashSet<String>,
}

impl ShellState {
    pub fn minimal() -> Self {
        Self {
            env: HashMap::new(),
            cwd: std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
            last_status: 0,
            functions: HashMap::new(),
            positional: Vec::new(),
            argv0: String::from("dsh"),
            pending_exit: None,
            exported: HashSet::new(),
        }
    }

    pub fn inherit_from_os() -> Self {
        let mut env: HashMap<String, String> = std::env::vars().collect();
        let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        env.insert("PWD".into(), cwd.to_string_lossy().into_owned());
        let exported: HashSet<String> = env.keys().cloned().collect();
        Self {
            env,
            cwd,
            last_status: 0,
            functions: HashMap::new(),
            positional: Vec::new(),
            argv0: String::from("dsh"),
            pending_exit: None,
            exported,
        }
    }

    pub fn get_var(&self, name: &str) -> Option<String> {
        self.env.get(name).cloned()
    }

    pub fn set_var(&mut self, name: impl Into<String>, value: impl Into<String>, export: bool) {
        let name = name.into();
        let value = value.into();
        self.env.insert(name.clone(), value);
        if export {
            self.exported.insert(name);
        }
    }

    pub fn set_and_export(&mut self, name: impl Into<String>, value: impl Into<String>) {
        let name = name.into();
        let value = value.into();
        self.env.insert(name.clone(), value);
        self.exported.insert(name);
    }

    pub fn export_name(&mut self, name: &str) {
        self.exported.insert(name.to_string());
    }

    pub fn exported_keys(&self) -> Vec<&str> {
        let mut ks: Vec<_> = self.exported.iter().map(|s| s.as_str()).collect();
        ks.sort();
        ks
    }

    pub fn unset(&mut self, name: &str) {
        self.env.remove(name);
        self.exported.remove(name);
    }

    pub fn child_env(&self, overlay: &[(String, String)]) -> HashMap<String, String> {
        let mut m = self.env.clone();
        for (k, v) in overlay {
            m.insert(k.clone(), v.clone());
        }
        m
    }
}
