mod cli;
mod crawl;
mod wayback;

use std::process::ExitCode;

use anyhow::Result;
use clap::Parser;

use crate::cli::{Cli, Commands};

#[tokio::main]
async fn main() -> ExitCode {
    match run().await {
        Ok(code) => ExitCode::from(code),
        Err(error) => {
            eprintln!("{error:#}");
            ExitCode::from(1)
        }
    }
}

async fn run() -> Result<u8> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Run(args) => cli::run_crawl(args).await,
        Commands::ListUrls(args) => cli::run_list_urls(args).await,
    }
}
