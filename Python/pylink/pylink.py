import os
import stat
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

__version__ = "0.2.0"

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "A modern wrapper for Windows mklink.\n\n"
        "Create a link: pylink TARGET [LINK] [OPTIONS]\n\n"
        "If TARGET is a directory and no type flag is given, pylink defaults to Junction "
        "(/J). In interactive mode it prompts you to choose Junction or Directory Symlink."
    ),
)

_CLI_KNOWN_SUBCOMMANDS = frozenset({"version", "info", "remove", "create-link"})
_CLI_GROUP_ONLY_FLAGS = frozenset({
    "-h",
    "--help",
    "--install-completion",
    "--show-completion",
})


def _normalize_cli_argv(argv: Optional[list[str]] = None) -> list[str]:
    """Assume create-link when the first token is not a known subcommand."""
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return argv
    first = argv[0]
    if first in ("--version", "-V"):
        return ["version"]
    if first in _CLI_KNOWN_SUBCOMMANDS or first in _CLI_GROUP_ONLY_FLAGS:
        return argv
    return ["create-link", *argv]


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


def format_link_display(link_path: Path, target_path: Path | str) -> str:
    """Format link path and destination as ``link -> dest``."""
    return f"{link_path} -> {target_path}"


_LINK_FLAG_DESCRIPTIONS: dict[str, str] = {
    "/J": "directory junction",
    "/D": "directory symbolic link",
    "/H": "hard link, same volume, files only",
    "": "file symbolic link",
}


def format_link_type(flag: str) -> str:
    """Return mklink-style flag with a short human-readable explanation."""
    desc = _LINK_FLAG_DESCRIPTIONS.get(flag)
    if desc is None:
        return flag
    if flag:
        return f"{flag} ({desc})"
    return desc


def show_link_context(link_path: Path, target_path: Path, flag: Optional[str] = None) -> None:
    """Print normalized absolute link creation context."""
    typer.echo(format_link_display(link_path, target_path))
    if flag is not None:
        typer.echo(f"Type:   {format_link_type(flag)}")


def normalize_absolute_path(path: Path) -> Path:
    """Normalize to absolute path without dereferencing symlinks/junctions."""
    return Path(os.path.abspath(str(path)))


def is_drive_root(path: Path) -> bool:
    """Return True when path points to a Windows drive root like D:\\."""
    return path.anchor and str(path).rstrip("\\/").lower() == path.anchor.rstrip("\\/").lower()


def validate_link_flags(*, directory: bool, junction: bool, hard: bool) -> Optional[str]:
    """Return an error message when mutually exclusive flags are set."""
    if sum([directory, junction, hard]) > 1:
        return "You cannot use --dir, --junction, and --hard simultaneously."
    return None


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


def _read_link_target(link_path: Path) -> Optional[str]:
    """Best-effort target path for a symlink/junction."""
    try:
        return os.readlink(str(link_path))
    except OSError:
        return None


def _remove_link_path(link_path: Path) -> None:
    """Remove a link path (symlink/junction/file), not a real directory tree."""
    if link_path.is_dir() and is_reparse_point(link_path):
        link_path.rmdir()
    elif link_path.is_dir():
        raise OSError(f"Refusing to remove non-link directory: {link_path}")
    else:
        link_path.unlink()


def _require_windows() -> None:
    if sys.platform != "win32":
        typer.secho("Error: pylink only supports Windows.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)


@app.command("version")
def version_cmd() -> None:
    """Show version."""
    typer.echo(f"pylink {__version__}")


@app.command("info")
def info_cmd(
    link_path_raw: Annotated[str, typer.Argument(help="Path to inspect")],
) -> None:
    """Show whether a path is a reparse point and its link target if readable."""
    _require_windows()
    link_path = normalize_absolute_path(Path(link_path_raw))
    if not path_lexists(link_path):
        typer.secho(f"Path does not exist: {link_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    is_link = is_reparse_point(link_path)
    if is_link:
        target = _read_link_target(link_path)
        typer.echo(format_link_display(link_path, target or "(unavailable)"))
    else:
        typer.echo(f"Path: {link_path} (not a link)")


@app.command("remove")
def remove_cmd(
    link_path_raw: Annotated[str, typer.Argument(help="Link path to remove")],
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove a symlink/junction (refuses real files/folders)."""
    _require_windows()
    link_path = normalize_absolute_path(Path(link_path_raw))
    if not path_lexists(link_path):
        typer.secho(f"Path does not exist: {link_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if not is_reparse_point(link_path):
        typer.secho("Error: Path is not a link/junction.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)
    if is_drive_root(link_path):
        typer.secho("Error: Refusing to remove a drive root.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)
    if not yes and not typer.confirm(f"Remove link at {link_path}?", default=False):
        typer.secho("Cancelled.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)
    try:
        _remove_link_path(link_path)
    except OSError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("Removed.", fg=typer.colors.GREEN)


def _run_create_link(
    target_path_raw: str,
    link_path_raw: Optional[str],
    *,
    directory: bool,
    junction: bool,
    hard: bool,
    yes: bool,
    replace: bool,
    no_validate_target: bool,
) -> None:
    _require_windows()

    flag_err = validate_link_flags(directory=directory, junction=junction, hard=hard)
    if flag_err:
        typer.secho(f"Error: {flag_err}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    target_path = Path(target_path_raw)
    link_path = Path(link_path_raw) if link_path_raw is not None else None

    if link_path is None:
        link_path = Path.cwd() / target_path.name

    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path
    if not link_path.is_absolute():
        link_path = Path.cwd() / link_path

    target_path = normalize_absolute_path(target_path).resolve(strict=False)
    link_path = normalize_absolute_path(link_path)

    if not no_validate_target and not target_path.exists():
        typer.secho("Error: Target path does not exist.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_path)
        raise typer.Exit(code=1)

    if path_lexists(link_path):
        if not replace:
            typer.secho("Error: Link path already exists.", fg=typer.colors.RED, bold=True)
            typer.secho(f"  Existing: {link_path}", fg=typer.colors.RED)
            typer.echo("Use --replace to remove and recreate the destination path.")
            raise typer.Exit(code=1)

        if is_drive_root(link_path):
            typer.secho("Error: Refusing to replace a drive root path.", fg=typer.colors.RED, bold=True)
            raise typer.Exit(code=1)

        existing_is_link = is_reparse_point(link_path)
        if yes and not existing_is_link:
            typer.secho("Error: Refusing non-interactive deletion of a real file/folder.", fg=typer.colors.RED, bold=True)
            typer.secho("Run again without --yes to complete interactive safety confirmation.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if not yes:
            if existing_is_link:
                if not typer.confirm(
                    f"'{link_path}' already exists as a link/junction. Remove and recreate it?",
                    default=False,
                ):
                    typer.secho("Cancelled.", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)
            else:
                typer.secho("WARNING: Existing destination is a real file/folder (not a link).", fg=typer.colors.YELLOW, bold=True)
                typer.secho("This will permanently delete it before creating the new link.", fg=typer.colors.YELLOW)
                if not typer.confirm("Confirm deletion of existing destination?", default=False):
                    typer.secho("Cancelled.", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)
                if not typer.confirm("Are you absolutely sure?", default=False):
                    typer.secho("Cancelled.", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)
                typed_path = typer.prompt("Type the full destination path exactly to continue")
                if typed_path.strip() != str(link_path):
                    typer.secho("Cancelled: typed path did not match.", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)

        try:
            if link_path.is_dir():
                if existing_is_link:
                    link_path.rmdir()
                else:
                    import shutil

                    shutil.rmtree(link_path)
            else:
                link_path.unlink()
        except OSError as remove_error:
            typer.secho("Error: Could not remove existing link path.", fg=typer.colors.RED, bold=True)
            typer.secho(f"  {remove_error}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    if link_path == target_path:
        typer.secho("Error: Link path and target path cannot be the same.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_path)
        typer.echo("\nSpecify a different link name or location. Example:")
        typer.echo(f"  pylink {target_path} {target_path.parent / (target_path.stem + '_link' + target_path.suffix)}")
        raise typer.Exit(code=1)

    flag = ""
    if directory:
        flag = "/D"
    elif junction:
        flag = "/J"
    elif hard:
        flag = "/H"
    elif target_path.exists() and target_path.is_dir():
        flag = resolve_default_directory_flag(yes=yes)

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
        if not typer.confirm("Proceed?", default=True):
            typer.secho("Cancelled.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

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
        if junction or flag == "/J":
            typer.echo("  • Junction creation failed (permissions or invalid target directory).")
        if hard:
            typer.echo("  • Hard links only work within the same volume.")
        if directory:
            typer.echo("  • Directory symlinks require a directory target and appropriate privileges.")
        typer.echo(f"\n  pylink create-link {target_path} {link_path}")
        raise typer.Exit(code=1)


@app.command("create-link")
def create_link(
    target_path_raw: Annotated[str, typer.Argument(help="TARGET path")],
    link_path_raw: Annotated[Optional[str], typer.Argument(help="LINK path (optional)")] = None,
    directory: bool = typer.Option(False, "--dir", "-d", help="Force a directory symbolic link (/D)"),
    junction: bool = typer.Option(False, "--junction", "-j", help="Force a directory junction (/J)"),
    hard: bool = typer.Option(False, "--hard", "-H", help="Force a hard link (/H, files only, same volume)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace existing path at LINK"),
    no_validate_target: bool = typer.Option(
        False, "--no-validate-target", help="Skip target existence/type validation"
    ),
) -> None:
    """Create a filesystem link (default when TARGET is provided)."""
    _run_create_link(
        target_path_raw,
        link_path_raw,
        directory=directory,
        junction=junction,
        hard=hard,
        yes=yes,
        replace=replace,
        no_validate_target=no_validate_target,
    )


if __name__ == "__main__":
    app(_normalize_cli_argv())
