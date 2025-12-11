import typer
import subprocess
import sys
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

# Initialize the app
app = typer.Typer(help="A modern wrapper for Windows mklink.")

@app.command()
def create_link(
    link_path: Annotated[Path, typer.Argument(help="The path where the link will be created")],
    target_path: Annotated[Path, typer.Argument(help="The existing file or directory to link to")],
    directory: bool = typer.Option(False, "--dir", "-d", help="Create a directory symbolic link (/D)"),
    junction: bool = typer.Option(False, "--junction", "-j", help="Create a Directory Junction (/J)"),
    hard: bool = typer.Option(False, "--hard", "-h", help="Create a hard link (/H)"),
):
    """
    Creates a filesystem link using the Windows mklink command.
    
    Defaults to a file symbolic link if no flags are provided.
    """
    
    # 1. Challenge: Validate Mutually Exclusive Options manually
    # Typer doesn't have "mutually_exclusive_group" like argparse yet, so we code it.
    flags_set = sum([directory, junction, hard])
    if flags_set > 1:
        typer.secho("Error: You cannot use --dir, --junction, and --hard simultaneously.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # 2. Determine the mklink flag
    flag = ""
    if directory:
        flag = "/D"
    elif junction:
        flag = "/J"
    elif hard:
        flag = "/H"

    # 3. Construct the command
    # Windows requires the command to be run inside a shell for mklink
    cmd = ["cmd", "/c", "mklink"]
    if flag:
        cmd.append(flag)
    
    # Convert Paths to strings
    cmd.append(str(link_path))
    cmd.append(str(target_path))

    # 4. Feedback to user
    typer.secho(f"Executing: {' '.join(cmd)}", fg=typer.colors.BLUE)

    try:
        # We assume 'target_path' exists, but mklink allows broken links, so we don't force-check it.
        subprocess.run(cmd, check=True, shell=False)
        typer.secho("Success!", fg=typer.colors.GREEN, bold=True)
        
    except subprocess.CalledProcessError as e:
        typer.secho(f"\nError: Failed to create link. (Exit Code: {e.returncode})", fg=typer.colors.RED)
        if e.returncode == 1:
            typer.echo("Tip: If you are not using --junction, ensure you are running as Administrator.")
        raise typer.Exit(code=e.returncode)

if __name__ == "__main__":
    app()