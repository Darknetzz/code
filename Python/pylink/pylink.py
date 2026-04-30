import typer
import sys
import os
import stat
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

# Initialize the app
app = typer.Typer(
    help=(
        "A modern wrapper for Windows mklink.\n\n"
        "If TARGET is a directory and no type flag is given, pylink defaults to Junction "
        "(/J). In interactive mode it prompts you to choose Junction or Directory Symlink."
    )
)


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


def normalize_absolute_path(path: Path) -> Path:
    """Normalize to absolute path without dereferencing symlinks/junctions."""
    return Path(os.path.abspath(str(path)))


def is_drive_root(path: Path) -> bool:
    """Return True when path points to a Windows drive root like D:\\."""
    return path.anchor and str(path).rstrip("\\/").lower() == path.anchor.rstrip("\\/").lower()


def resolve_default_directory_flag(yes: bool) -> str:
    """
    Pick directory link type when target is a directory and user did not choose
    an explicit flag. Defaults to junction for better Windows compatibility.
    """
    if yes:
        return "/J"

    choice = typer.prompt(
        "Directory target detected. Choose link type: [J]unction or [D]irectory symlink",
        default="J",
    ).strip().upper()
    if choice == "D":
        return "/D"
    return "/J"


def create_windows_link(link_path: Path, target_path: Path, flag: str) -> str:
    """
    Create a link using Win32 APIs (same results as mklink, without cmd.exe).

    cmd/mklink can mis-parse paths containing ``!`` or other specials; the C API
    accepts any valid NT path.
    """
    target_s = str(target_path)
    link_s = str(link_path)
    if flag == "/H":
        os.link(target_s, link_s)
        return f"os.link({target_s!r}, {link_s!r})"
    if flag == "/J":
        import _winapi

        _winapi.CreateJunction(target_s, link_s)
        return f"_winapi.CreateJunction({target_s!r}, {link_s!r})"
    if flag == "/D":
        os.symlink(target_s, link_s, target_is_directory=True)
        return f"os.symlink({target_s!r}, {link_s!r}, target_is_directory=True)"
    os.symlink(target_s, link_s, target_is_directory=False)
    return f"os.symlink({target_s!r}, {link_s!r})"


@app.command()
def create_link(
    target_path_raw: Annotated[str, typer.Argument(help="TARGET: Existing file/directory path to point at (required unless --no-validate-target)")],
    link_path_raw: Annotated[Optional[str], typer.Argument(help="LINK: Path to create (defaults to CWD/<target basename> if omitted; always shown as absolute path)")] = None,
    directory: bool = typer.Option(False, "--dir", "-d", help="Force a directory symbolic link (/D)"),
    junction: bool = typer.Option(False, "--junction", "-j", help="Force a directory junction (/J); recommended for Windows directory links"),
    hard: bool = typer.Option(False, "--hard", "-h", help="Force a hard link (/H, files only, same volume)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace existing path at LINK path (requires extra confirmation for non-link files/folders)"),
    no_validate_target: bool = typer.Option(False, "--no-validate-target", help="Skip target existence/type validation (allows intentionally broken symlinks; advanced)"),
):
    """
    Creates a filesystem link using Windows APIs (equivalent to mklink).

    Default type behavior:
    - Directory target + no type flag: prompt (interactive) or default to junction (/J) with --yes.
    - File target + no type flag: file symbolic link.
    """
    if sys.platform != "win32":
        typer.secho("Error: pylink only supports Windows.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)

    target_path = Path(target_path_raw)
    link_path = Path(link_path_raw) if link_path_raw is not None else None

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

    # Normalize to absolute paths so nothing reinterprets relative segments
    # against an unexpected working directory.
    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path
    if not link_path.is_absolute():
        link_path = Path.cwd() / link_path

    target_path = normalize_absolute_path(target_path).resolve(strict=False)
    link_path = normalize_absolute_path(link_path)

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

    # 4. Determine the mklink flag.
    # For directory targets with no explicit flag, prompt in interactive mode and
    # default to junction to avoid common symlink policy issues on Windows.
    flag = ""
    if directory:
        flag = "/D"
    elif junction:
        flag = "/J"
    elif hard:
        flag = "/H"
    elif target_path.exists() and target_path.is_dir():
        flag = resolve_default_directory_flag(yes=yes)

    # Validate target type for explicit flag choices.
    if not no_validate_target and flag in ("/D", "/J") and not target_path.is_dir():
        typer.secho("Error: Directory links require a directory target.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_path, flag)
        raise typer.Exit(code=1)
    if not no_validate_target and flag == "/H" and target_path.is_dir():
        typer.secho("Error: Hard links only support file targets.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_path, flag)
        raise typer.Exit(code=1)

    if not yes:
        show_link_context(link_path, target_path, flag)
        confirmed = typer.confirm("Proceed?", default=True)
        if not confirmed:
            typer.secho("Cancelled.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

    # 5–6. Create link via Win32 APIs (not cmd/mklink — avoids path parsing bugs).
    typer.secho("Executing:", fg=typer.colors.BLUE)

    try:
        detail = create_windows_link(link_path, target_path, flag)
        typer.secho(f"  {detail}", fg=typer.colors.BLUE)
        typer.secho("Success!", fg=typer.colors.GREEN, bold=True)
        show_link_context(link_path, target_path, flag)

    except OSError as e:
        typer.secho("\n==============================", fg=typer.colors.RED)
        typer.secho("  FAILED TO CREATE LINK", fg=typer.colors.RED, bold=True)
        typer.secho("==============================\n", fg=typer.colors.RED)
        typer.secho(f"  {e}", fg=typer.colors.RED)

        typer.secho("\nPossible causes:", fg=typer.colors.YELLOW, bold=True)
        typer.echo("  • The link path already exists. Remove it and retry.")
        typer.echo("  • Insufficient privileges. For symlinks, run as Administrator or enable Developer Mode.")
        if junction or (flag == "/J"):
            typer.echo("  • Junction creation failed (permissions or invalid target directory).")
        if hard:
            typer.echo("  • Hard links only work within the same volume.")
        if directory:
            typer.echo("  • Directory symlinks require a directory target and appropriate privileges.")
        if flag in ("", "/D") and not junction:
            typer.echo("\nTip: For file/directory symlinks, ensure Developer Mode or Administrator.")

        try:
            if link_path.exists():
                typer.secho("\nSuggestion:", fg=typer.colors.BLUE, bold=True)
                typer.echo(f"  Remove existing link/file and retry:\n    del \"{link_path}\"\n    pylink {target_path} {link_path}")
        except Exception:
            pass
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()