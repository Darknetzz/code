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
    
    # Apply offset and clamp at 00:00:00,000
    # shifted = max(timedelta(0), delta + timedelta(seconds=offset_seconds))
    shifted = delta + timedelta(seconds=offset_seconds)
    if shifted < timedelta(0):
        raise ValueError("Shift results in negative timestamp! Aborting to prevent file corruption.")
    
    total_seconds = int(shifted.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    millis = int(shifted.microseconds / 1000)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

@app.command()
def shift(
    srt_path: Optional[Path] = typer.Argument(
        None,
        help="Path to the .srt file.",
    ),
    seconds: Optional[float] = typer.Option(
        None,
        "--seconds",
        "-s",
        help="Seconds to shift (positive = forward, negative = backward).",
    ),
):
    """Shift SRT subtitle timestamps forward or backward."""
    
    # Prompt for file if missing or invalid
    while srt_path is None or not srt_path.is_file():
        if srt_path is not None and not srt_path.is_file():
            console.print(f"[red]File not found: {srt_path}[/red]")
        raw_path = Prompt.ask("Enter path to .srt file")
        srt_path = Path(raw_path.strip('"\''))  # Clean quotes from drag-and-drop

    # Prompt for shift amount if missing
    if seconds is None:
        console.print("\n[dim]Tip: Use negative numbers to shift backward (e.g., -90 for 1m 30s), positive to shift forward.[/dim]")
        seconds = FloatPrompt.ask("Enter shift offset in seconds")

    content = srt_path.read_text(encoding="utf-8", errors="replace")
    timestamp_pattern = r"\d{2}:\d{2}:\d{2},\d{3}"

    updated_content = re.sub(
        timestamp_pattern,
        lambda m: shift_timestamp(m, seconds),
        content,
    )

    srt_path.write_text(updated_content, encoding="utf-8")
    
    direction = "forward" if seconds >= 0 else "backward"
    console.print(f"\n[bold green]Success:[/bold green] Shifted [cyan]{srt_path.name}[/cyan] {abs(seconds)}s {direction}.")

if __name__ == "__main__":
    app()