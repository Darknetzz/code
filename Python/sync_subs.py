import subprocess
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.prompt import Confirm

app = typer.Typer(add_completion=False)
console = Console()

@app.command()
def sync(
    target_dir: Path = typer.Argument(
        Path("."),
        help="Directory containing MKV files. Defaults to current directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    sub_stream: str = typer.Option(
        "0:s:0",
        "--stream",
        "-s",
        help="Subtitle stream index (e.g. 0:s:0, 0:s:1).",
    ),
    overwrite: Optional[bool] = typer.Option(
        None,
        "--overwrite/--no-overwrite",
        "-y/-n",
        help="Overwrite existing .srt files. If omitted, you will be prompted per existing file.",
    ),
):
    """Batch extract and sync integrated MKV subtitles using ffsubsync."""
    mkv_files = list(target_dir.glob("*.mkv"))

    if not mkv_files:
        console.print(f"[yellow]No .mkv files found in {target_dir}[/yellow]")
        raise typer.Exit()

    for mkv in mkv_files:
        final_srt = mkv.with_suffix(".srt")
        tmp_srt = mkv.with_suffix(".tmp.srt")

        console.print(f"\n[bold blue]Processing:[/bold blue] {mkv.name}")

        # Handle existing .srt overwrite logic
        if final_srt.exists():
            should_overwrite = overwrite
            if should_overwrite is None:
                should_overwrite = Confirm.ask(
                    f"File [bold cyan]{final_srt.name}[/bold cyan] already exists. Overwrite?",
                    default=False,
                )

            if not should_overwrite:
                console.print("  [yellow]Skipped:[/yellow] File exists and overwrite was declined.")
                continue

        # 1. Extract integrated subtitle stream
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(mkv),
            "-map", sub_stream,
            str(tmp_srt),
        ]

        res = subprocess.run(ffmpeg_cmd)

        if res.returncode != 0 or not tmp_srt.exists() or tmp_srt.stat().st_size == 0:
            console.print(f"  [red]Skipped:[/red] No subtitle track found at stream {sub_stream}.")
            if tmp_srt.exists():
                tmp_srt.unlink()
            continue

        # 2. Run ffsubsync
        ffs_cmd = ["ffs", str(mkv), "-i", str(tmp_srt), "-o", str(final_srt)]

        with console.status("[dim]Running ffsubsync...[/dim]", spinner="dots"):
            ffs_res = subprocess.run(ffs_cmd, capture_output=True, text=True)

        # Cleanup temporary extracted file
        if tmp_srt.exists():
            tmp_srt.unlink()

        if ffs_res.returncode == 0:
            console.print(f"  [bold green]Success:[/bold green] Created {final_srt.name}")
        else:
            console.print(f"  [bold red]Error:[/bold red] {ffs_res.stderr.strip() or 'ffsubsync failed.'}")

if __name__ == "__main__":
    app()