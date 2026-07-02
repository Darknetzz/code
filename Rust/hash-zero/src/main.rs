mod cli;
mod hash;
mod output;
mod search;

use anyhow::Result;
use clap::Parser;
use rayon::ThreadPoolBuilder;

use crate::cli::{validate_zero_target, Command, FindArgs, VerifyArgs};
use crate::hash::verify_input;
use crate::output::{
    print_error, print_find_human, print_find_json, print_verify_human, print_verify_json,
};
use crate::search::find_hash;

fn main() {
    std::process::exit(match run() {
        Ok(code) => code,
        Err(error) => {
            print_error(&error.to_string());
            1
        }
    });
}

fn run() -> Result<i32> {
    let cli = cli::Cli::parse();

    match cli.command {
        Command::Find(args) => run_find(args),
        Command::Verify(args) => run_verify(args),
    }
}

fn run_find(args: FindArgs) -> Result<i32> {
    configure_threads(args.threads)?;
    validate_shared(&args.shared)?;

    let result = find_hash(&args)?;

    if args.shared.json {
        print_find_json(&result);
    } else {
        print_find_human(&result);
    }

    Ok(0)
}

fn run_verify(args: VerifyArgs) -> Result<i32> {
    validate_shared(&args.shared)?;

    let outcome = verify_input(
        &args.input,
        args.shared.algorithm,
        args.shared.zeros,
        args.shared.side(),
        args.shared.unit,
    )?;

    if args.shared.json {
        print_verify_json(&outcome);
    } else {
        print_verify_human(&outcome);
    }

    Ok(if outcome.meets_target { 0 } else { 1 })
}

fn validate_shared(shared: &cli::SharedArgs) -> Result<()> {
    validate_zero_target(shared.algorithm, shared.unit, shared.zeros)
}

fn configure_threads(threads: Option<std::num::NonZeroUsize>) -> Result<()> {
    if let Some(count) = threads {
        ThreadPoolBuilder::new()
            .num_threads(count.get())
            .build_global()?;
    }
    Ok(())
}
