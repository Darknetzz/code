import typer
import subprocess
import sys
import os
import stat
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

# Initialize the app
app = typer.Typer(help="A modern wrapper for Windows mklink.")


def path_lexists(path: Path) -> bool:
    """Return True if path exists, including broken links."""
    return os.path.lexists(str(path))


def is_reparse_point(path: Path) -> bool:
    """
    Return True for Windows reparse points (symlinks/junctions/mount points).
    Uses lstat so broken links can still be identified.
    """
    try:
        st = os.lstat(str(path))
    except OSError:
        return False
    return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def show_link_context(link_path: Path, target_path: Path, flag: str = "") -> None:
    """Print normalized absolute link creation context."""
    typer.echo(f"Link:   {link_path}")
    typer.echo(f"Target: {target_path}")
    if flag:
        typer.echo(f"Type:   {flag}")


def is_drive_root(path: Path) -> bool:
    """Return True when path points to a Windows drive root like D:\\."""
    return path.anchor and str(path).rstrip("\\/").lower() == path.anchor.rstrip("\\/").lower()


@app.command()
def create_link(
    target_path: Annotated[Path, typer.Argument(help="TARGET: Existing file/directory the link points to (required)")],
    link_path: Optional[Path] = typer.Argument(None, help="LINK: Path to create (defaults to CWD/<target basename> if omitted)"),
    directory: bool = typer.Option(False, "--dir", "-d", help="Create a directory symbolic link (/D)"),
    junction: bool = typer.Option(False, "--junction", "-j", help="Create a Directory Junction (/J)"),
    hard: bool = typer.Option(False, "--hard", "-h", help="Create a hard link (/H)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace existing path at LINK path (requires extra confirmation for non-link files/folders)"),
    no_validate_target: bool = typer.Option(False, "--no-validate-target", help="Allow non-existent target paths (advanced)"),
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

    # Normalize to absolute paths so cmd/mklink cannot reinterpret relative
    # paths against an unexpected working directory.
    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path
    if not link_path.is_absolute():
        link_path = Path.cwd() / link_path

    target_path = target_path.resolve(strict=False)
    link_path = link_path.resolve(strict=False)

    # 3. Validate target before any creation attempt (unless user opts out).
    if not no_validate_target and not target_path.exists():
        typer.secho("Error: Target path does not exist.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_path)
        raise typer.Exit(code=1)

    # 3.5 Prevent accidental overwrite of existing paths.
    # We allow --replace, but require additional safeguards for real files/folders.
    if path_lexists(link_path):
        if not replace:
            typer.secho("Error: Link path already exists.", fg=typer.colors.RED, bold=True)
            typer.secho(f"  Existing: {link_path}", fg=typer.colors.RED)
            typer.echo("Use --replace to remove and recreate the destination path.")
            raise typer.Exit(code=1)

        if is_drive_root(link_path):
            typer.secho("Error: Refusing to replace a drive root path.", fg=typer.colors.RED, bold=True)
            typer.secho(f"  Blocked path: {link_path}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        existing_is_link = is_reparse_point(link_path)
        if yes and not existing_is_link:
            typer.secho("Error: Refusing non-interactive deletion of a real file/folder.", fg=typer.colors.RED, bold=True)
            typer.secho("Run again without --yes to complete interactive safety confirmation.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if not yes:
            if existing_is_link:
                confirmed_replace = typer.confirm(
                    f"'{link_path}' already exists as a link/junction. Remove and recreate it?",
                    default=False,
                )
                if not confirmed_replace:
                    typer.secho("Cancelled.", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)
            else:
                typer.secho("WARNING: Existing destination is a real file/folder (not a link).", fg=typer.colors.YELLOW, bold=True)
                typer.secho("This will permanently delete it before creating the new link.", fg=typer.colors.YELLOW)
                confirmed_1 = typer.confirm("Confirm deletion of existing destination?", default=False)
                if not confirmed_1:
                    typer.secho("Cancelled.", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)
                confirmed_2 = typer.confirm("Are you absolutely sure?", default=False)
                if not confirmed_2:
                    typer.secho("Cancelled.", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)
                typed_path = typer.prompt("Type the full destination path exactly to continue")
                if typed_path.strip() != str(link_path):
                    typer.secho("Cancelled: typed path did not match.", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)

        try:
            if link_path.is_dir():
                if existing_is_link:
                    # Junctions and directory symlinks are removed with rmdir.
                    link_path.rmdir()
                else:
                    # Real directory removal requires recursive delete.
                    import shutil
                    shutil.rmtree(link_path)
            else:
                link_path.unlink()
        except OSError as remove_error:
            typer.secho("Error: Could not remove existing link path.", fg=typer.colors.RED, bold=True)
            typer.secho(f"  {remove_error}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

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

    # Validate target type for explicit flag choices.
    if not no_validate_target and flag in ("/D", "/J") and not target_path.is_dir():
        typer.secho("Error: Directory links require a directory target.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_path, flag)
        raise typer.Exit(code=1)
    if not no_validate_target and flag == "/H" and target_path.is_dir():
        typer.secho("Error: Hard links only support file targets.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_path, flag)
        raise typer.Exit(code=1)

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

    if not yes:
        show_link_context(link_path, target_path, flag)
        confirmed = typer.confirm("Proceed?", default=True)
        if not confirmed:
            typer.secho("Cancelled.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

    # 6. Feedback to user
    typer.secho(f"Executing: cmd /c {mklink_command}", fg=typer.colors.BLUE)

    try:
        # We assume 'target_path' exists, but mklink allows broken links, so we don't force-check it.
        subprocess.run(cmd, check=True, shell=False)
        typer.secho("Success!", fg=typer.colors.GREEN, bold=True)
        show_link_context(link_path, target_path, flag)
        
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