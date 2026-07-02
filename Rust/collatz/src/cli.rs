use clap::Parser;

#[derive(Debug, Parser)]
#[command(name = "collatz", about = "Compute Collatz sequences for arbitrary-size integers")]
pub struct Cli {
    /// Starting positive integer or arithmetic expression.
    pub number: String,

    /// Print only the step count.
    #[arg(long)]
    pub steps_only: bool,

    /// Print the full sequence.
    #[arg(long)]
    pub show_sequence: bool,

    /// Report the maximum value reached.
    #[arg(long)]
    pub peak: bool,

    /// Emit JSON report.
    #[arg(long)]
    pub json: bool,

    /// Show calculation progress on stderr.
    #[arg(long)]
    pub progress: bool,

    /// Disable progress output (including the default on interactive stderr).
    #[arg(long)]
    pub no_progress: bool,
}
