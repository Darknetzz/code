mod cli;
mod config;
mod icmp;
mod models;
mod output;
mod resolve;
mod runner;
mod stats;
mod subprocess;
mod tcp;

use std::io;

use anyhow::Result;
use clap::Parser;

use crate::cli::Cli;
use crate::config::{build_run_config, load_file_config};
use crate::output::{print_error, print_human_results, print_json, ReplySink};

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
    let multi_host = run_config.hosts.len() > 1;

    let stdout = io::stdout();
    let mut handle = stdout.lock();
    let mut sink = ReplySink::new(
        &mut handle,
        run_config.quiet,
        run_config.json,
        multi_host,
    );

    let results = runner::run_probes(&run_config, &mut sink).await?;

    if run_config.json {
        print_json(&results);
    } else {
        print_human_results(&results, multi_host, run_config.quiet);
    }

    let exit_code = if results.iter().all(|result| result.ok()) {
        0
    } else {
        1
    };
    Ok(exit_code)
}
