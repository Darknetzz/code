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
    /// When a builtin requests `return` inside a function body.
    pub pending_return: Option<i32>,
    /// Nesting depth for user-defined function calls (`return` is invalid at 0).
    pub function_depth: u32,
    exported: HashSet<String>,
}

impl ShellState {
    /// Basename of argv[0] (e.g. `darkshell.exe` or `dsh` via symlink).
    pub fn program_name_from_args() -> String {
        std::env::args()
            .next()
            .and_then(|p| {
                std::path::Path::new(&p)
                    .file_name()
                    .map(|n| n.to_string_lossy().into_owned())
            })
            .unwrap_or_else(|| String::from("darkshell"))
    }

    pub fn minimal() -> Self {
        Self {
            env: HashMap::new(),
            cwd: std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
            last_status: 0,
            functions: HashMap::new(),
            positional: Vec::new(),
            argv0: Self::program_name_from_args(),
            pending_exit: None,
            pending_return: None,
            function_depth: 0,
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
            argv0: Self::program_name_from_args(),
            pending_exit: None,
            pending_return: None,
            function_depth: 0,
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
        let mut m = HashMap::new();
        for k in &self.exported {
            if let Some(v) = self.env.get(k) {
                m.insert(k.clone(), v.clone());
            }
        }
        for (k, v) in overlay {
            m.insert(k.clone(), v.clone());
        }
        m
    }
}

/// Temporary overlay for prefix assignments (`VAR=value cmd`).
pub struct EnvOverlay {
    saved: Vec<(String, Option<String>)>,
}

impl EnvOverlay {
    pub fn apply(st: &mut ShellState, overlay: &[(String, String)]) -> Self {
        let mut saved = Vec::with_capacity(overlay.len());
        for (k, v) in overlay {
            saved.push((k.clone(), st.env.get(k).cloned()));
            st.env.insert(k.clone(), v.clone());
        }
        Self { saved }
    }

    pub fn restore(self, st: &mut ShellState) {
        for (k, old) in self.saved {
            match old {
                Some(v) => {
                    st.env.insert(k, v);
                }
                None => {
                    st.env.remove(&k);
                }
            }
        }
    }
}
