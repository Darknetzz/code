mod cli;
mod collatz;
mod expr;
mod output;
mod progress;

use anyhow::Result;
use clap::Parser;

use crate::cli::Cli;
use crate::collatz::run_collatz;
use crate::output::{print_error, print_human, print_json};
use crate::progress::progress_enabled_by_default;

fn main() {
    std::process::exit(match run() {
        Ok(()) => 0,
        Err(error) => {
            print_error(&error.to_string());
            1
        }
    });
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    let show_peak = !cli.steps_only || cli.peak;
    let show_progress = cli.progress || (!cli.no_progress && progress_enabled_by_default(cli.json));
    let result = run_collatz(&cli.number, cli.show_sequence, show_progress)?;

    if cli.json {
        print_json(&result, cli.show_sequence);
    } else {
        print_human(
            &result,
            cli.steps_only,
            show_peak,
            cli.show_sequence,
        );
    }

    Ok(())
}
