//! After each build, create `dsh` -> `darkshell` in the output directory.

use std::env;
use std::path::{Path, PathBuf};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");

    let profile = env::var("PROFILE").expect("PROFILE");
    let target_dir = env::var("CARGO_TARGET_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR")).join("target")
        });

    let host = env::var("HOST").expect("HOST");
    let target = env::var("TARGET").expect("TARGET");
    let bin_dir = if target == host {
        target_dir.join(&profile)
    } else {
        target_dir.join(target).join(&profile)
    };

    #[cfg(windows)]
    let (primary, alias) = ("darkshell.exe", "dsh.exe");
    #[cfg(not(windows))]
    let (primary, alias) = ("darkshell", "dsh");

    if let Err(err) = create_relative_symlink(&bin_dir, primary, alias) {
        println!(
            "cargo:warning=failed to create {alias} -> {primary} in {}: {err}",
            bin_dir.display()
        );
    }
}

fn create_relative_symlink(bin_dir: &Path, primary: &str, alias: &str) -> std::io::Result<()> {
    std::fs::create_dir_all(bin_dir)?;

    let link_path = bin_dir.join(alias);
    if link_path.exists() {
        std::fs::remove_file(&link_path)?;
    }

    #[cfg(unix)]
    std::os::unix::fs::symlink(primary, link_path)?;
    #[cfg(windows)]
    std::os::windows::fs::symlink_file(primary, link_path)?;

    Ok(())
}
