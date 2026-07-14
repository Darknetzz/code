//! Embeds compile metadata and the Windows executable icon.

fn main() {
    #[cfg(windows)]
    embed_windows_icon();

    let ts = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S UTC");
    println!("cargo:rustc-env=PATHMAN_BUILD_TIME={}", ts);
    println!("cargo:rerun-if-changed=assets/pathman.ico");
    println!("cargo:rerun-if-changed=build.rs");
}

#[cfg(windows)]
fn embed_windows_icon() {
    let mut res = winres::WindowsResource::new();
    res.set_icon("assets/pathman.ico");
    if let Err(e) = res.compile() {
        eprintln!("winres: failed to embed pathman.ico: {e}");
        std::process::exit(1);
    }
}
