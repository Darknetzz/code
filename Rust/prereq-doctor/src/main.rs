mod checks;
mod cli;
mod config;
mod models;
mod output;

use anyhow::Result;
use clap::Parser;

use crate::checks::{run_builtin_checks, run_custom_checks};
use crate::cli::Cli;
use crate::config::load_file_config;
use crate::models::CheckStatus;
use crate::output::{print_error, print_human, print_json};

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

    let mut results = run_builtin_checks(&cli.only).await;
    results.extend(run_custom_checks(&file.checks, &cli.only).await);

    if cli.json {
        print_json(&results);
    } else {
        print_human(&results);
    }

    let failed_required = results.iter().any(|result| {
        result.status == CheckStatus::Fail && (result.required || cli.strict)
    });

    Ok(if failed_required { 1 } else { 0 })
}
