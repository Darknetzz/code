//! pathman — cross-platform GUI for editing user and system PATH and environment variables.

use std::sync::Arc;

mod app;
mod config;
mod env_model;
mod path_model;
mod persist;
mod row_icons;

/// Minimum inner size so the top toolbar (scopes, save row, filters, checkboxes) stays on one line.
const VIEWPORT_MIN_INNER: [f32; 2] = [1380.0, 480.0];

fn print_version() {
    let built = env!("PATHMAN_BUILD_TIME");
    println!("pathman {} (built {})", env!("CARGO_PKG_VERSION"), built);
}

fn print_help() {
    println!("pathman — cross-platform GUI for editing user and system PATH and environment variables.");
    println!();
    println!("USAGE:");
    println!("    pathman");
    println!("        Open the graphical PATH editor.");
    #[cfg(windows)]
    {
        println!("    pathman --apply-machine <file>");
        println!("        Apply machine PATH from a file (internal elevated helper).");
    }
    #[cfg(unix)]
    {
        println!("    pathman --apply-system-unix <file>");
        println!("        Apply system PATH from a file (internal elevated helper).");
    }
    println!();
    println!("OPTIONS:");
    println!("    -h, --help");
    println!("        Print this help message.");
    println!("    -v, --version");
    println!("        Print version and compile timestamp.");
}

fn main() -> eframe::Result<()> {
    let args: Vec<String> = std::env::args().collect();

    let rest: Vec<&String> = args.iter().skip(1).collect();
    if rest.iter().any(|a| matches!(a.as_str(), "-h" | "--help")) {
        print_help();
        return Ok(());
    }
    if rest
        .iter()
        .any(|a| matches!(a.as_str(), "-v" | "--version"))
    {
        print_version();
        return Ok(());
    }

    #[cfg(windows)]
    if args.len() == 3 && args[1] == "--apply-machine" {
        if let Err(e) = persist::apply_machine_from_file(&args[2]) {
            eprintln!("{e:#}");
            std::process::exit(1);
        }
        return Ok(());
    }

    #[cfg(unix)]
    if args.len() == 3 && args[1] == "--apply-system-unix" {
        if let Err(e) = persist::apply_system_from_file(&args[2]) {
            eprintln!("{e:#}");
            std::process::exit(1);
        }
        return Ok(());
    }

    let app_icon = Arc::new(
        eframe::icon_data::from_png_bytes(include_bytes!("../assets/pathman.png"))
            .expect("embedded app icon is a valid PNG"),
    );

    let native_options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_title("pathman")
            .with_icon(app_icon)
            .with_inner_size([VIEWPORT_MIN_INNER[0], 680.0])
            .with_min_inner_size(VIEWPORT_MIN_INNER),
        ..Default::default()
    };

    eframe::run_native(
        "pathman",
        native_options,
        Box::new(|cc| Ok(Box::new(app::PathmanApp::new(cc)))),
    )
}
