use std::path::Path;

use sysinfo::Disks;

#[derive(Debug, Clone, Default)]
pub struct VolumeInfo {
    pub mount: String,
    pub total: u64,
    pub available: u64,
}

impl VolumeInfo {
    pub fn used(&self) -> u64 {
        self.total.saturating_sub(self.available)
    }
}

/// Best-effort match of a path to a mounted volume.
pub fn volume_for_path(path: &Path) -> Option<VolumeInfo> {
    let disks = Disks::new_with_refreshed_list();
    let path_s = path.to_string_lossy();
    let mut best: Option<(usize, VolumeInfo)> = None;

    for disk in disks.list() {
        let mount = disk.mount_point().to_string_lossy().to_string();
        if mount.is_empty() {
            continue;
        }
        let matches = {
            #[cfg(windows)]
            {
                path_s
                    .to_ascii_lowercase()
                    .starts_with(&mount.trim_end_matches('\\').to_ascii_lowercase())
                    || path_s
                        .to_ascii_lowercase()
                        .starts_with(&mount.to_ascii_lowercase())
            }
            #[cfg(not(windows))]
            {
                path_s.starts_with(&mount)
            }
        };
        if matches {
            let score = mount.len();
            let info = VolumeInfo {
                mount: mount.clone(),
                total: disk.total_space(),
                available: disk.available_space(),
            };
            if best.as_ref().map(|(s, _)| score > *s).unwrap_or(true) {
                best = Some((score, info));
            }
        }
    }
    best.map(|(_, v)| v)
}
