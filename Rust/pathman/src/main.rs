//! pathman — cross-platform GUI for editing user and system PATH.

mod app;
mod config;
mod path_model;
mod persist;

fn main() -> eframe::Result<()> {
    let args: Vec<String> = std::env::args().collect();

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

    let native_options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_title("pathman")
            .with_inner_size([720.0, 560.0])
            .with_min_inner_size([520.0, 400.0]),
        ..Default::default()
    };

    eframe::run_native(
        "pathman",
        native_options,
        Box::new(|cc| Ok(Box::new(app::PathmanApp::new(cc)))),
    )
}
