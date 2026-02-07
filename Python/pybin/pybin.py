import sys
import typer
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# Use UTF-8 for stdout/stderr so emojis work on Windows (e.g. when cp1252 is default)
def _ensure_utf8():
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleOutputCP(65001)  # UTF-8
            kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and getattr(stream, "encoding", "").lower() != "utf-8":
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


_ensure_utf8()

from rich.console import Console

app = typer.Typer()
console = Console()

# ============================================================================ #
#                               FUNCTION: cprint                               #
# ============================================================================ #
def cprint(message: str, type: str = "", style: str = "bold green", **kwargs) -> None:
    prefix = f"[{datetime.now().strftime('%H:%M:%S')}]"
    style  = ""
    type   = type.lower()
    
    if type == "error":
        style = "red"
        prefix = "❌"
    elif type == "warning":
        style = "yellow"
        prefix = "⚠️"
    elif type == "info":
        style = "blue"
        prefix = "ℹ️"
    elif type == "success":
        style = "green"
        prefix = "✅"
    message = f"{prefix}  {message}"
    console.print(message, style=style, **kwargs)


# ============================================================================ #
#                                FUNCTION: main                                #
# ============================================================================ #
@app.command()
def main(
    file: Path = typer.Argument(..., help="Python file to process"),
    keep_spec: bool = typer.Option(
        True,
        "--keep-spec/--no-keep-spec",
        help="Keep the .spec file after building (default: keep)",
        show_default=True,
    ),
    keep_build: bool = typer.Option(False, "--keep-build", help="Keep the build directory after building"),
    output_dir: Path = typer.Option(None, "--output-dir", help="Optional output directory for the built executable (defaults to script's dist/ folder)"),
):
    """
    CLI tool that accepts a single Python file as argument.
    Compiles it with PyInstaller and cleans up build artifacts.
    """
    if not file.exists():
        console.print(f"[red]✗ Error:[/red] File '{file}' does not exist.", style="bold")
        raise typer.Exit(code=1)
    
    if file.suffix != ".py":
        console.print(f"[red]✗ Error:[/red] '{file}' is not a Python file.", style="bold")
        raise typer.Exit(code=1)
    
    console.print(f"[cyan]📦 Processing:[/cyan] {file}", style="bold")

    # Determine base paths (use script directory to keep outputs next to the script)
    base_dir = file.resolve().parent
    dist_path = output_dir.resolve() if output_dir else base_dir / "dist"
    work_path = base_dir / "build"
    spec_path = base_dir
    spec_file = spec_path / f"{file.stem}.spec"

    # Ensure output directory exists
    dist_path.mkdir(parents=True, exist_ok=True)

    # Run pyinstaller with explicit paths
    # If a .spec file exists, use it directly to preserve custom settings
    if spec_file.exists():
        console.print(f"[green]✓ Found existing .spec file:[/green] {spec_file.name}")

        # If the source file is newer than the spec, regenerate the spec
        try:
            src_mtime = file.stat().st_mtime
            spec_mtime = spec_file.stat().st_mtime
        except Exception:
            src_mtime = None
            spec_mtime = None

        if src_mtime is not None and spec_mtime is not None and src_mtime > spec_mtime:
            console.print("[yellow]⚠ Source is newer than .spec; regenerating .spec (backup saved)[/yellow]")
            # Backup existing spec
            backup_spec = spec_file.with_suffix(spec_file.suffix + ".bak")
            try:
                shutil.copy2(spec_file, backup_spec)
            except Exception:
                console.print("[red]✗ Failed to backup existing .spec; continuing without backup[/red]")

            makespec_cmd = [
                "pyi-makespec",
                "--onefile",
                f"--specpath={spec_path}",
                str(file.resolve()),
            ]
            mk = subprocess.run(makespec_cmd, capture_output=True, text=True, cwd=str(base_dir))
            if mk.returncode != 0:
                console.print("[red]✗ pyi-makespec failed; using existing .spec[/red]")
                console.print(mk.stderr, style="red")
            else:
                console.print("[green]✓ .spec regenerated[/green]")

        cmd = [
            "pyinstaller",
            f"--distpath={dist_path}",
            f"--workpath={work_path}",
            str(spec_file),
        ]
    else:
        console.print("[yellow]⚙ Generating new .spec file[/yellow]")
        cmd = [
            "pyinstaller",
            "--onefile",
            f"--distpath={dist_path}",
            f"--workpath={work_path}",
            f"--specpath={spec_path}",
            str(file.resolve()),  # Use absolute path to avoid cross-drive issues
        ]
    # Run from the file's directory to avoid Windows cross-drive path issues
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(base_dir))
    if result.returncode != 0:
        console.print("[red]✗ PyInstaller failed:[/red]", style="bold")
        console.print(result.stderr, style="red")
        raise typer.Exit(code=1)
    
    console.print("[green]✓ PyInstaller completed successfully[/green]", style="bold")
    
    # Clean up build directory (cross-platform) if not keeping it
    if not keep_build:
        if work_path.exists():
            shutil.rmtree(work_path)
            console.print("[dim]  Cleaned up build directory[/dim]")
    else:
        console.print("[yellow]  Keeping build directory (--keep-build)[/yellow]")
    
    # Clean up spec file if not keeping it
    if not keep_spec:
        if spec_file.exists():
            spec_file.unlink()
            console.print("[dim]  Cleaned up .spec file[/dim]")
    elif keep_spec and not spec_file.exists():
        # Only show message if user explicitly set --keep-spec but no spec was generated
        pass
    
    ext = file.suffix if file.suffix else ""
    console.print(f"\n[green]✓ Build complete:[/green] [cyan]{dist_path / file.stem}{ext}[/cyan]", style="bold")



if __name__ == "__main__":
    app()