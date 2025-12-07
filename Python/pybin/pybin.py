import typer, subprocess, shutil
from pathlib import Path

app = typer.Typer()

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
        typer.echo(f"Error: File '{file}' does not exist.", err=True)
        raise typer.Exit(code=1)
    
    if file.suffix != ".py":
        typer.echo(f"Error: '{file}' is not a Python file.", err=True)
        raise typer.Exit(code=1)
    
    typer.echo(f"Processing Python file: {file}")

    # Determine base paths (use script directory to keep outputs next to the script)
    base_dir = file.resolve().parent
    dist_path = output_dir.resolve() if output_dir else base_dir / "dist"
    work_path = base_dir / "build"
    spec_path = base_dir

    # Ensure output directory exists
    dist_path.mkdir(parents=True, exist_ok=True)

    # Run pyinstaller with explicit paths
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
        typer.echo(f"Error running pyinstaller: {result.stderr}", err=True)
        raise typer.Exit(code=1)
    
    typer.echo("PyInstaller completed successfully")
    
    # Clean up build directory (cross-platform) if not keeping it
    if not keep_build:
        if work_path.exists():
            shutil.rmtree(work_path)
            typer.echo("Cleaned up build directory")
        else:
            typer.echo("Build directory already cleaned")
    else:
        typer.echo("Keeping build directory (--keep-build)")
    
    # Clean up spec file if not keeping it
    spec_file = spec_path / f"{file.stem}.spec"
    if not keep_spec:
        if spec_file.exists():
            spec_file.unlink()
            typer.echo("Cleaned up .spec file")
        else:
            typer.echo(".spec file already cleaned")
    else:
        typer.echo("Keeping .spec file (--keep-spec)")



if __name__ == "__main__":
    app()