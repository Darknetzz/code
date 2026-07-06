mod checks;
mod cli;
mod config;
mod models;
mod output;
mod runner;

use anyhow::Result;
use clap::Parser;

use crate::cli::Cli;
use crate::config::{build_run_config, load_file_config};
use crate::models::CheckStatus;
use crate::output::{print_error, print_fallback_notice, print_human, print_json};
use crate::runner::run_checks;

#[tokio::main]
async fn main() {
    std::process::exit(match run().await {
        Ok(code) => code,
        Err(error) => {
            print_error(&error.to_string());
            2
        }
    });
}

async fn run() -> Result<i32> {
    let cli = Cli::parse();
    let file = load_file_config(cli.config.as_deref())?;
    let run_config = build_run_config(&cli, file)?;
    let results = run_checks(&run_config).await?;

    if cli.json {
        print_json(&results);
    } else {
        if run_config.using_fallback_targets {
            print_fallback_notice();
        }
        print_human(&results);
    }

    let exit_code = if results
        .iter()
        .any(|result| result.status == CheckStatus::Fail)
    {
        1
    } else {
        0
    };
    Ok(exit_code)
}
