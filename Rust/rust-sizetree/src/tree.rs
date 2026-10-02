use std::path::{Path, PathBuf};

use crate::models::DirInfo;
use crate::models::ScanStats;

pub type NodeId = usize;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScanPhase {
    Idle,
    Running,
    Done,
    Cancelled,
}

#[derive(Debug, Clone)]
pub struct TreeNode {
    pub path: PathBuf,
    pub size: u64,
    pub file_count: u64,
    pub dir_count: u64,
    pub children: Vec<NodeId>,
    pub parent: Option<NodeId>,
    pub error: Option<String>,
    pub is_dir: bool,
    /// False while this directory is still being walked.
    pub complete: bool,
}

impl TreeNode {
    pub fn name(&self) -> String {
        self.path
            .file_name()
            .and_then(|s| s.to_str())
            .map(str::to_string)
            .unwrap_or_else(|| self.path.display().to_string())
    }
}

#[derive(Debug)]
pub struct ScanTree {
    pub nodes: Vec<TreeNode>,
    pub root: Option<NodeId>,
    pub stats: ScanStats,
    pub phase: ScanPhase,
}

impl ScanTree {
    pub fn new() -> Self {
        Self {
            nodes: Vec::new(),
            root: None,
            stats: ScanStats::default(),
            phase: ScanPhase::Idle,
        }
    }

    pub fn clear(&mut self) {
        self.nodes.clear();
        self.root = None;
        self.stats = ScanStats::default();
        self.phase = ScanPhase::Idle;
    }

    pub fn get(&self, id: NodeId) -> Option<&TreeNode> {
        self.nodes.get(id)
    }

    pub fn insert_dir(&mut self, path: &Path, parent: Option<NodeId>) -> NodeId {
        let id = self.nodes.len();
        self.nodes.push(TreeNode {
            path: path.to_path_buf(),
            size: 0,
            file_count: 0,
            dir_count: 0,
            children: Vec::new(),
            parent,
            error: None,
            is_dir: true,
            complete: false,
        });
        if let Some(p) = parent {
            self.nodes[p].children.push(id);
            self.bubble_counts(p, 0, 0, 1);
            self.stats.dirs += 1;
        } else {
            self.root = Some(id);
        }
        id
    }

    pub fn insert_file(&mut self, path: &Path, parent: NodeId, size: u64) -> NodeId {
        let id = self.nodes.len();
        self.nodes.push(TreeNode {
            path: path.to_path_buf(),
            size,
            file_count: 1,
            dir_count: 0,
            children: Vec::new(),
            parent: Some(parent),
            error: None,
            is_dir: false,
            complete: true,
        });
        self.nodes[parent].children.push(id);
        self.bubble_counts(parent, size, 1, 0);
        self.stats.files += 1;
        self.stats.size += size;
        id
    }

    /// Add size/counts to `from` and all of its ancestors (does not touch global stats).
    pub fn bubble_counts(&mut self, from: NodeId, size: u64, files: u64, dirs: u64) {
        let mut cur = Some(from);
        while let Some(id) = cur {
            let node = &mut self.nodes[id];
            node.size += size;
            node.file_count += files;
            node.dir_count += dirs;
            cur = node.parent;
        }
    }

    pub fn set_leaf_totals(
        &mut self,
        id: NodeId,
        size: u64,
        files: u64,
        dirs: u64,
        error: Option<String>,
    ) {
        let node = &mut self.nodes[id];
        node.size = size;
        node.file_count = files;
        node.dir_count = dirs;
        node.error = error;
        node.complete = true;
        if let Some(parent) = node.parent {
            self.bubble_counts(parent, size, files, dirs);
        }
    }

    pub fn mark_complete(&mut self, id: NodeId) {
        if let Some(node) = self.nodes.get_mut(id) {
            node.complete = true;
        }
    }

    pub fn set_error(&mut self, id: NodeId, error: String) {
        if let Some(node) = self.nodes.get_mut(id) {
            node.error = Some(error);
        }
    }

    pub fn sort_children(&mut self, id: NodeId) {
        let mut kids = self.nodes[id].children.clone();
        kids.sort_by(|&a, &b| {
            self.nodes[b]
                .size
                .cmp(&self.nodes[a].size)
                .then_with(|| self.nodes[a].name().cmp(&self.nodes[b].name()))
        });
        self.nodes[id].children = kids;
    }

    pub fn to_dir_info(&self) -> Option<DirInfo> {
        let root = self.root?;
        Some(self.node_to_dir_info(root))
    }

    fn node_to_dir_info(&self, id: NodeId) -> DirInfo {
        let node = &self.nodes[id];
        let mut children: Vec<DirInfo> = node
            .children
            .iter()
            .map(|&cid| self.node_to_dir_info(cid))
            .collect();
        children.sort_by(|a, b| b.size.cmp(&a.size));
        DirInfo {
            path: node.path.clone(),
            size: node.size,
            file_count: node.file_count,
            dir_count: node.dir_count,
            children,
            error: node.error.clone(),
        }
    }

    /// Snapshot child ids of `id`, sorted by current size (for GUI display).
    pub fn sorted_children(&self, id: NodeId) -> Vec<NodeId> {
        let Some(node) = self.nodes.get(id) else {
            return Vec::new();
        };
        let mut kids = node.children.clone();
        kids.sort_by(|&a, &b| {
            self.nodes[b]
                .size
                .cmp(&self.nodes[a].size)
                .then_with(|| self.nodes[a].name().cmp(&self.nodes[b].name()))
        });
        kids
    }
}

impl Default for ScanTree {
    fn default() -> Self {
        Self::new()
    }
}
