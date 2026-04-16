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
    target_path: Annotated[Path, typer.Argument(help="TARGET: Existing file/directory the link points to (required)")],
    link_path: Optional[Path] = typer.Argument(None, help="LINK: Path to create (defaults to CWD/<target basename> if omitted)"),
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

    # 2. Resolve missing link using sensible defaults
    # If link_path is omitted, default to CWD/<target basename>
    if link_path is None:
        link_path = Path.cwd() / target_path.name

    # 3. Validate that link_path and target_path are not the same
    try:
        link_resolved = link_path.resolve()
        target_resolved = target_path.resolve()
        if link_resolved == target_resolved:
            typer.secho("Error: Link path and target path cannot be the same.", fg=typer.colors.RED, bold=True)
            typer.secho(f"  Link:   {link_path}", fg=typer.colors.RED)
            typer.secho(f"  Target: {target_path}", fg=typer.colors.RED)
            typer.echo("\nSpecify a different link name or location. Example:")
            typer.echo(f"  pylink create-link {target_path} {target_path.parent / (target_path.stem + '4win' + target_path.suffix)}")
            raise typer.Exit(code=1)
    except OSError:
        # Paths may not exist yet; just compare the paths as-is
        if link_path.resolve() == target_path.resolve():
            typer.secho("Error: Link path and target path cannot be the same.", fg=typer.colors.RED, bold=True)
            typer.secho(f"  Link:   {link_path}", fg=typer.colors.RED)
            typer.secho(f"  Target: {target_path}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    # 4. Determine the mklink flag
    # If target exists and is a directory, default to /D unless a flag is explicit.
    flag = ""
    if directory:
        flag = "/D"
    elif junction:
        flag = "/J"
    elif hard:
        flag = "/H"
    elif target_path.exists() and target_path.is_dir():
        flag = "/D"

    # 5. Construct the command
    # Windows requires mklink to run under cmd. Build a cmd-native command
    # string with explicit double quotes so spaces are handled correctly.
    mklink_parts = ["mklink"]
    if flag:
        mklink_parts.append(flag)
    mklink_parts.append(f"\"{link_path}\"")
    mklink_parts.append(f"\"{target_path}\"")
    mklink_command = " ".join(mklink_parts)
    cmd = ["cmd", "/c", mklink_command]

    # 6. Feedback to user
    typer.secho(f"Executing: cmd /c {mklink_command}", fg=typer.colors.BLUE)

    try:
        # We assume 'target_path' exists, but mklink allows broken links, so we don't force-check it.
        subprocess.run(cmd, check=True, shell=False)
        typer.secho("Success!", fg=typer.colors.GREEN, bold=True)
        
    except subprocess.CalledProcessError as e:
        # Emphasized error output with actionable hints
        typer.secho("\n==============================", fg=typer.colors.RED)
        typer.secho("  FAILED TO CREATE LINK", fg=typer.colors.RED, bold=True)
        typer.secho("==============================\n", fg=typer.colors.RED)
        typer.secho(f"Exit Code: {e.returncode}", fg=typer.colors.RED)
        typer.secho("Command:", fg=typer.colors.RED)
        typer.secho(f"  cmd /c {mklink_command}", fg=typer.colors.RED)

        # Common pitfalls and guidance
        typer.secho("\nPossible causes:", fg=typer.colors.YELLOW, bold=True)
        typer.echo("  • The link path already exists. Remove it and retry.")
        typer.echo("  • Arguments swapped. Correct order is: LINK first, TARGET second.")
        typer.echo("  • Insufficient privileges. For symlinks, run as Administrator or enable Developer Mode.")
        if junction:
            typer.echo("  • Junctions typically require Administrator.")
        if hard:
            typer.echo("  • Hard links only work within the same volume.")
        if directory:
            typer.echo("  • Use --dir for directory symlinks; for folders consider --junction.")

        # Extra tip for non-junction attempts
        if e.returncode == 1 and not junction:
            typer.echo("\nTip: If you are not using --junction, ensure you are running as Administrator.")
        
        # Show suggested fix if the link path exists
        try:
            if link_path.exists():
                typer.secho("\nSuggestion:", fg=typer.colors.BLUE, bold=True)
                typer.echo(f"  Remove existing link/file and retry:\n    del \"{link_path}\"\n    mklink {'/D ' if directory else ('/H ' if hard else '')}\"{link_path}\" \"{target_path}\"")
        except Exception:
            pass
        raise typer.Exit(code=e.returncode)

if __name__ == "__main__":
    app()