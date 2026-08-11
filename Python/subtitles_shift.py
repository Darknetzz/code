import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.prompt import FloatPrompt, Prompt

app = typer.Typer(add_completion=False)
console = Console()

def shift_timestamp(match: re.Match, offset_seconds: float) -> str:
    time_str = match.group(0)
    t = datetime.strptime(time_str, "%H:%M:%S,%f")
    delta = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second, microseconds=t.microsecond)
    
    shifted = delta + timedelta(seconds=offset_seconds)
    if shifted < timedelta(0):
        raise ValueError("Shift results in negative timestamp!")
    
    total_seconds = int(shifted.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    millis = int(shifted.microseconds / 1000)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

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
    """Shift SRT subtitle timestamps for a single file or a whole directory."""
    
    while target_path is None or not target_path.exists():
        if target_path is not None and not target_path.exists():
            console.print(f"[red]Path not found: {target_path}[/red]")
        raw_path = Prompt.ask("Enter path to .srt file or directory")
        target_path = Path(raw_path.strip('"\''))

    if seconds is None:
        console.print("\n[dim]Tip: Use negative numbers to shift backward (e.g., -65), positive to shift forward.[/dim]")
        seconds = FloatPrompt.ask("Enter shift offset in seconds")

    if target_path.is_file():
        srt_files = [target_path]
    else:
        # Exclude temp files if any remain
        srt_files = [f for f in target_path.glob("*.srt") if not f.name.endswith(".tmp.srt")]

    if not srt_files:
        console.print(f"[yellow]No .srt files found at {target_path}[/yellow]")
        raise typer.Exit()

    direction = "forward" if seconds >= 0 else "backward"
    timestamp_pattern = r"\d{2}:\d{2}:\d{2},\d{3}"

    for srt in srt_files:
        try:
            content = srt.read_text(encoding="utf-8", errors="replace")
            updated_content = re.sub(
                timestamp_pattern,
                lambda m: shift_timestamp(m, seconds),
                content,
            )
            srt.write_text(updated_content, encoding="utf-8")
            console.print(f" [bold green]Success:[/bold green] Shifted [cyan]{srt.name}[/cyan] {abs(seconds)}s {direction}.")
        except Exception as e:
            console.print(f" [bold red]Failed:[/bold red] {srt.name} - {e}")

if __name__ == "__main__":
    app()