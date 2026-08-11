from pathlib import Path
from datetime import timedelta
from typing import Optional
import typer
import srt
from rich.console import Console
from rich.prompt import FloatPrompt, Prompt

app = typer.Typer(add_completion=False)
console = Console()

@app.command()
def shift(
    target_path: Optional[Path] = typer.Argument(
        None,
        help="Path to an .srt file or directory containing .srt files.",
    ),
    seconds: Optional[float] = typer.Option(
        None,
        "--seconds",
        "-s",
        help="Seconds to shift (positive = forward, negative = backward).",
    ),
):
    """Shift SRT subtitle timestamps using the native 'srt' library."""
    
    # Prompt for path if missing
    while target_path is None or not target_path.exists():
        if target_path is not None and not target_path.exists():
            console.print(f"[red]Path not found: {target_path}[/red]")
        raw_path = Prompt.ask("Enter path to .srt file or directory")
        target_path = Path(raw_path.strip('"\''))

    # Prompt for offset if missing
    if seconds is None:
        console.print("\n[dim]Tip: Use negative numbers to shift backward (e.g., -65), positive to shift forward.[/dim]")
        seconds = FloatPrompt.ask("Enter shift offset in seconds")

    srt_files = [target_path] if target_path.is_file() else list(target_path.glob("*.srt"))

    if not srt_files:
        console.print(f"[yellow]No .srt files found at {target_path}[/yellow]")
        raise typer.Exit()

    shift_delta = timedelta(seconds=seconds)
    direction = "forward" if seconds >= 0 else "backward"

    for srt_file in srt_files:
        if srt_file.name.endswith(".tmp.srt"):
            continue

        try:
            content = srt_file.read_text(encoding="utf-8", errors="replace")
            subtitles = list(srt.parse(content))

            # Apply timedelta directly to parsed Subtitle objects
            for sub in subtitles:
                new_start = sub.start + shift_delta
                new_end = sub.end + shift_delta
                
                if new_start < timedelta(0):
                    raise ValueError("Shift results in negative timestamps!")

                sub.start = new_start
                sub.end = new_end

            # Re-compose into proper SRT format
            srt_file.write_text(srt.compose(subtitles), encoding="utf-8")
            console.print(f" [bold green]Success:[/bold green] Shifted [cyan]{srt_file.name}[/cyan] {abs(seconds)}s {direction}.")

        except Exception as e:
            console.print(f" [bold red]Failed:[/bold red] {srt_file.name} - {e}")

if __name__ == "__main__":
    app()