mod browser;
mod cli;
mod file_kind;
mod gui;
mod models;
mod progress;
mod report;
mod scan;
mod tree;

use std::process::ExitCode;

use anyhow::Result;
use clap::Parser;

use crate::cli::{Cli, Commands};

fn main() -> ExitCode {
    match run() {
        Ok(code) => ExitCode::from(code),
        Err(error) => {
            eprintln!("{error:#}");
            ExitCode::from(2)
        }
    }
}

fn run() -> Result<u8> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Scan(args) => cli::run_scan(args),
        Commands::Report(args) => cli::run_report(args),
        Commands::Gui(args) => cli::run_gui(args),
        Commands::Version => {
            println!("SizeTree v0.1.0");
            Ok(0)
        }
    }
}
