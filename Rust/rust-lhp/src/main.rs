use std::process::ExitCode;

use anyhow::{bail, Result};
use clap::{Parser, Subcommand};

use rust_lhp::{build_tls_client, build_tls_server, interactive_client, run_server, send_packet};

#[derive(Parser)]
#[command(
    name = "rust-lhp",
    about = "Lab Hop Protocol CLI",
    version
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Server(ServerArgs),
    Client(ClientArgs),
}

#[derive(Parser)]
struct ServerArgs {
    #[arg(long)]
    tls: bool,
    #[arg(long)]
    certfile: Option<String>,
    #[arg(long)]
    keyfile: Option<String>,
    #[arg(long, default_value = "0.0.0.0")]
    host: String,
    #[arg(long, default_value_t = 8888)]
    port: u16,
}

#[derive(Parser)]
struct ClientArgs {
    host: String,
    port: u16,
    #[arg(long)]
    tls: bool,
    #[arg(long)]
    certfile: Option<String>,
    #[arg(long, short = 'i')]
    interactive: bool,
    #[arg(long)]
    cmd: Option<u8>,
    #[arg(long)]
    data: Option<String>,
}

#[tokio::main]
async fn main() -> ExitCode {
    match run().await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error:#}");
            ExitCode::from(1)
        }
    }
}

async fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Server(args) => {
            if args.tls && (args.certfile.is_none() || args.keyfile.is_none()) {
                bail!("--certfile and --keyfile required with --tls");
            }
            let tls = if args.tls {
                Some(build_tls_server(
                    args.certfile.as_deref().unwrap(),
                    args.keyfile.as_deref().unwrap(),
                )?)
            } else {
                None
            };
            run_server(&args.host, args.port, tls).await
        }
        Commands::Client(args) => {
            let tls = if args.tls {
                Some(build_tls_client(args.certfile.as_deref())?)
            } else {
                None
            };
            if args.interactive {
                if args.cmd.is_some() {
                    bail!("cannot use --cmd with --interactive");
                }
                interactive_client(&args.host, args.port, tls).await
            } else if let Some(cmd) = args.cmd {
                let data = args.data.unwrap_or_default();
                send_packet(&args.host, args.port, cmd, data.as_bytes(), tls).await
            } else {
                bail!("specify --interactive or --cmd");
            }
        }
    }
}
