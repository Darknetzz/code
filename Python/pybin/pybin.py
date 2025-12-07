import typer, subprocess, shutil
from pathlib import Path
from rich.console import Console

app = typer.Typer()
console = Console()

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
        cmd = [
            "pyinstaller",
            f"--distpath={dist_path}",
            f"--workpath={work_path}",
            str(spec_file),
        ]
    else:
        console.print(f"[yellow]⚙ Generating new .spec file[/yellow]")
        cmd = [
            "pyinstaller",
            "--onefile",
            f"--distpath={dist_path}",
            f"--workpath={work_path}",
            f"--specpath={spec_path}",
            str(file),
        ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]✗ PyInstaller failed:[/red]", style="bold")
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
    
    console.print(f"\n[green]✓ Build complete:[/green] [cyan]{dist_path / file.stem}.exe[/cyan]", style="bold")



if __name__ == "__main__":
    app()