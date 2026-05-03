//! Embeds the compile time into the binary (see `std::env!` in `main.rs`).

fn main() {
    let ts = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S UTC");
    println!("cargo:rustc-env=PATHMAN_BUILD_TIME={}", ts);
}
