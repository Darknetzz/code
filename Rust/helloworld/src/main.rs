use clap::{ArgAction, Parser};

#[derive(Parser, Debug)]
#[command(
    name = "helloworld",
    about = "A tiny demo CLI that prints greetings.",
    version,
    author
)]
struct Cli {
    /// Name to greet (positional). Defaults to "world" if omitted.
    name: Option<String>,

    /// Greeting word to use (e.g., Hello, Hi, Hey)
    #[arg(short, long, default_value = "Hello")]
    greeting: String,

    /// How many times to print the greeting
    #[arg(short, long, default_value_t = 1)]
    count: u32,

    /// Increase verbosity (-v, -vv, -vvv)
    #[arg(short, long, action = ArgAction::Count)]
    verbose: u8,

    /// Optional output file; if set, writes there instead of stdout
    #[arg(short, long)]
    output: Option<std::path::PathBuf>,
}

fn main() {
    let cli = Cli::parse();

    let name = cli.name.as_deref().unwrap_or("world");

    let mut out: Box<dyn std::io::Write> = match cli.output.as_deref() {
        Some(path) => match std::fs::File::create(path) {
            Ok(f) => Box::new(f),
            Err(e) => {
                eprintln!("error: failed to create output file: {e}");
                std::process::exit(2);
            }
        },
        None => Box::new(std::io::stdout()),
    };

    if cli.verbose > 0 {
        eprintln!(
            "[verbose:{}] greeting='{}' name='{}' count={} output={}",
            cli.verbose,
            cli.greeting,
            name,
            cli.count,
            cli.output
                .as_ref()
                .map(|p| p.display().to_string())
                .unwrap_or_else(|| "<stdout>".to_string())
        );
    }

    for i in 1..=cli.count {
        let line = format!("{} {}!\n", cli.greeting, name);
        if let Err(e) = out.write_all(line.as_bytes()) {
            eprintln!("error: failed to write (iteration {i}): {e}");
            std::process::exit(3);
        }
    }
}
