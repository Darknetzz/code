import typer, subprocess
from pathlib import Path

app = typer.Typer()

@app.command()
def main(file: Path = typer.Argument(..., help="Python file to process")):
    """
    CLI tool that accepts a single Python file as argument.
    """
    if not file.exists():
        typer.echo(f"Error: File '{file}' does not exist.", err=True)
        raise typer.Exit(code=1)
    
    if file.suffix != ".py":
        typer.echo(f"Error: '{file}' is not a Python file.", err=True)
        raise typer.Exit(code=1)
    
    typer.echo(f"Processing Python file: {file}")
    # Add your file processing logic here

    # Run pyinstaller
    result = subprocess.run(["pyinstaller", "--onefile", str(file)], capture_output=True, text=True)
    if result.returncode != 0:
        typer.echo(f"Error running pyinstaller: {result.stderr}", err=True)
        raise typer.Exit(code=1)
    
    typer.echo("PyInstaller completed successfully")
    
    # Clean up build directory
    subprocess.run(["rm", "-rf", "build"], shell=True)
    spec_file = file.with_suffix(".spec")
    if spec_file.exists():
        spec_file.unlink()
    typer.echo("Cleaned up build directory")



if __name__ == "__main__":
    app()