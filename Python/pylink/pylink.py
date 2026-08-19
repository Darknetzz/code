import os
import stat
import sys
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer

__version__ = "0.3.0"

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "A modern wrapper for Windows mklink.\n\n"
        "Create a link: pylink TARGET [LINK] [OPTIONS]\n\n"
        "If TARGET is a directory and no type flag is given, pylink defaults to Junction "
        "(/J) on local NTFS with an absolute target. Relative targets and network paths "
        "default to a directory symlink (/D) so the stored target stays portable."
    ),
)

_CLI_KNOWN_SUBCOMMANDS = frozenset({"version", "info", "remove", "create-link"})
_CLI_GROUP_ONLY_FLAGS = frozenset({
    "-h",
    "--help",
    "--install-completion",
    "--show-completion",
})

DRIVE_REMOTE = 4
_WINERR_PRIVILEGE_NOT_HELD = 1314
_WINERR_SMB_UNSUPPORTED = frozenset({1, 5, 50})


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


def show_link_context(
    link_path: Path,
    stored_target: Path | str,
    flag: Optional[str] = None,
    *,
    resolved_target: Optional[Path] = None,
) -> None:
    """Print link creation context, showing the stored target string."""
    typer.echo(format_link_display(link_path, stored_target))
    if resolved_target is not None and str(resolved_target) != str(stored_target):
        typer.echo(f"Resolves to: {resolved_target}")
    if flag is not None:
        typer.echo(f"Type:   {format_link_type(flag)}")


def normalize_absolute_path(path: Path) -> Path:
    """Normalize to absolute path without dereferencing symlinks/junctions."""
    return Path(os.path.abspath(str(path)))


def is_drive_root(path: Path) -> bool:
    """Return True when path points to a Windows drive root like D:\\."""
    return path.anchor and str(path).rstrip("\\/").lower() == path.anchor.rstrip("\\/").lower()


def is_unc_path(path: Path | str) -> bool:
    """Return True for UNC paths, including ``\\\\?\\UNC\\`` extended form."""
    s = str(path).replace("/", "\\")
    upper = s.upper()
    if upper.startswith("\\\\?\\UNC\\") or upper.startswith("\\??\\UNC\\"):
        return True
    if s.startswith("\\\\?\\") or s.startswith("\\??\\"):
        return False
    return s.startswith("\\\\")


def _default_drive_type(root: str) -> int:
    import ctypes

    return int(ctypes.windll.kernel32.GetDriveTypeW(root))


def is_remote_path(
    path: Path | str,
    *,
    drive_type_fn: Optional[Callable[[str], int]] = None,
) -> bool:
    """Return True for UNC paths or mapped network drives (DRIVE_REMOTE)."""
    if is_unc_path(path):
        return True
    s = str(path).replace("/", "\\")
    if s.startswith("\\\\?\\") or s.startswith("\\??\\"):
        s = s[4:]
        if s.upper().startswith("UNC\\"):
            return True
    drive = os.path.splitdrive(s)[0]
    if len(drive) == 2 and drive[1] == ":":
        root = drive + "\\"
        if drive_type_fn is None:
            if sys.platform != "win32":
                return False
            drive_type_fn = _default_drive_type
        return int(drive_type_fn(root)) == DRIVE_REMOTE
    return False


def target_looks_nonportable(target: str) -> bool:
    """True when a stored target has a drive letter, UNC, or NT prefix (not Linux-safe)."""
    s = str(target).replace("/", "\\")
    if is_unc_path(s):
        return True
    if s.startswith("\\??\\") or s.startswith("\\\\?\\"):
        return True
    drive = os.path.splitdrive(s)[0]
    return bool(drive)


def user_target_is_relative(target_raw: str) -> bool:
    """Return True when the user-supplied TARGET is not an absolute path."""
    return not Path(target_raw).is_absolute()


def resolve_user_target(target_raw: str, *, cwd: Optional[Path] = None) -> Path:
    """Absolute, normalized target for existence checks (does not follow reparse points)."""
    cwd = cwd or Path.cwd()
    raw = Path(target_raw)
    if not raw.is_absolute():
        raw = cwd / raw
    return normalize_absolute_path(raw)


def stored_symlink_target(
    target_raw: str,
    link_path: Path,
    *,
    force_relative: bool,
    cwd: Optional[Path] = None,
) -> str:
    """
    Target string stored in a symlink reparse point.

    Relative user input (or ``force_relative``) is rewritten relative to the
    link's parent and uses POSIX separators so Linux can follow the same string.
    """
    cwd = cwd or Path.cwd()
    resolved = resolve_user_target(target_raw, cwd=cwd)
    if not (force_relative or user_target_is_relative(target_raw)):
        return str(resolved)

    link_parent = normalize_absolute_path(link_path.parent)
    try:
        rel = os.path.relpath(str(resolved), start=str(link_parent))
    except ValueError:
        return str(resolved)
    return rel.replace("\\", "/")


def prefer_directory_symlink(*, relative_target: bool, remote: bool) -> bool:
    """Junction cannot preserve a relative target and cannot live on a network path."""
    return relative_target or remote


def junction_remote_error_message(
    link_path: Path,
    target_path: Path,
    *,
    drive_type_fn: Optional[Callable[[str], int]] = None,
) -> Optional[str]:
    """Error text when a junction is requested on a UNC/mapped path; else None."""
    if not (
        is_remote_path(link_path, drive_type_fn=drive_type_fn)
        or is_remote_path(target_path, drive_type_fn=drive_type_fn)
    ):
        return None
    return (
        "Junctions require a local NTFS volume. "
        "This path is on a network share; use a directory symlink (--dir) "
        "with a relative target instead."
    )


def validate_link_flags(*, directory: bool, junction: bool, hard: bool) -> Optional[str]:
    """Return an error message when mutually exclusive flags are set."""
    if sum([directory, junction, hard]) > 1:
        return "You cannot use --dir, --junction, and --hard simultaneously."
    return None


def validate_relative_flag(*, relative: bool, junction: bool, hard: bool) -> Optional[str]:
    """Return an error when --relative is combined with APIs that require an absolute target."""
    if relative and (junction or hard):
        return "--relative cannot be used with --junction or --hard (those APIs require an absolute target)."
    return None


def resolve_default_directory_flag(
    yes: bool,
    *,
    relative_target: bool = False,
    remote: bool = False,
) -> str:
    """
    Pick directory link type when target is a directory and user did not choose
    an explicit flag. Junction remains the local-NTFS convenience default.
    """
    prefer_symlink = prefer_directory_symlink(relative_target=relative_target, remote=remote)
    default_flag = "/D" if prefer_symlink else "/J"
    if yes:
        return default_flag

    if remote:
        typer.echo("This path is on a network share. Junctions require local NTFS.")
    if relative_target:
        typer.echo("Target is relative. Junctions always store an absolute path, which breaks Linux consumers.")

    default_choice = "D" if prefer_symlink else "J"
    choice = typer.prompt(
        "Directory target detected. Choose link type: "
        "[J]unction (absolute, local NTFS only) or "
        "[D]irectory symlink (portable if the target stays relative)",
        default=default_choice,
    ).strip().upper()
    if choice == "D":
        return "/D"
    if choice == "J":
        return "/J"
    return default_flag


def posix_ln_suggestion(stored_target: str, link_path: Path) -> str:
    """POSIX ``ln -s`` equivalent for a version-pointer style link."""
    posix_target = stored_target.replace("\\", "/")
    if target_looks_nonportable(posix_target):
        posix_target = Path(stored_target.replace("/", "\\")).name
    return f"ln -s {posix_target} {link_path.name}"


def create_link_error_hints(
    exc: OSError,
    *,
    flag: str,
    remote: bool,
    stored_target: str,
    link_path: Path,
) -> list[str]:
    """Human-readable causes after a failed create."""
    hints = [
        "The link path already exists. Remove it and retry.",
        "Insufficient privileges. For symlinks, run as Administrator or enable Developer Mode.",
    ]
    winerr = getattr(exc, "winerror", None)
    if winerr == _WINERR_PRIVILEGE_NOT_HELD:
        hints.append("WinError 1314: a required privilege is not held (enable Developer Mode or run elevated).")
    if flag == "/J":
        hints.append("Junctions require a local NTFS volume. They cannot be created on a mapped/UNC share.")
    if flag == "/H":
        hints.append("Hard links only work within the same volume.")
    if flag == "/D":
        hints.append("Directory symlinks require a directory target and appropriate privileges.")
    if remote:
        if winerr in _WINERR_SMB_UNSUPPORTED or winerr is None:
            hints.append(
                "The NAS/SMB server may not support Windows reparse points "
                "(Samba needs a recent version that handles FSCTL_SET_REPARSE_POINT)."
            )
        hints.append(f"From Linux, create a POSIX symlink instead: {posix_ln_suggestion(stored_target, link_path)}")
        hints.append("Windows then sees a normal directory (no R2R policy).")
    return hints


def create_windows_link(link_path: Path, target: str, flag: str) -> str:
    """
    Create a link using Win32 APIs (same results as mklink, without cmd.exe).

    cmd/mklink can mis-parse paths containing ``!`` or other specials; the C API
    accepts any valid NT path. Symlink ``target`` is stored verbatim.
    """
    link_s = str(link_path)
    if flag == "/H":
        os.link(target, link_s)
        return f"os.link({target!r}, {link_s!r})"
    if flag == "/J":
        import _winapi

        _winapi.CreateJunction(target, link_s)
        return f"_winapi.CreateJunction({target!r}, {link_s!r})"
    if flag == "/D":
        os.symlink(target, link_s, target_is_directory=True)
        return f"os.symlink({target!r}, {link_s!r}, target_is_directory=True)"
    os.symlink(target, link_s, target_is_directory=False)
    return f"os.symlink({target!r}, {link_s!r})"


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


def _warn_r2r_if_needed(link_path: Path, flag: str) -> None:
    if flag in ("/J", "/H"):
        return
    if not is_remote_path(link_path):
        return
    typer.secho(
        "Warning: Windows will not follow a remote-to-remote symlink until R2R is enabled:",
        fg=typer.colors.YELLOW,
    )
    typer.echo("  fsutil behavior set SymlinkEvaluation R2R:1")
    typer.echo("Linux/Samba may still follow a POSIX symlink created on the server.")


def _warn_nonportable_target(stored_target: str, flag: str) -> None:
    if flag in ("/J", "/H"):
        return
    if not target_looks_nonportable(stored_target):
        return
    typer.secho(
        "Warning: stored target is absolute (drive letter or UNC). Linux will not follow this link.",
        fg=typer.colors.YELLOW,
    )


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
        if target:
            if target_looks_nonportable(target):
                typer.secho(
                    "Note: stored target is absolute (drive letter, UNC, or NT prefix); "
                    "Linux will not follow this path.",
                    fg=typer.colors.YELLOW,
                )
            else:
                typer.echo("Stored target is relative (portable across Windows and Linux).")
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
    relative: bool,
    no_validate_target: bool,
) -> None:
    _require_windows()

    flag_err = validate_link_flags(directory=directory, junction=junction, hard=hard)
    if flag_err:
        typer.secho(f"Error: {flag_err}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    rel_err = validate_relative_flag(relative=relative, junction=junction, hard=hard)
    if rel_err:
        typer.secho(f"Error: {rel_err}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    target_raw_path = Path(target_path_raw)
    relative_input = user_target_is_relative(target_path_raw)

    link_path = Path(link_path_raw) if link_path_raw is not None else Path.cwd() / target_raw_path.name
    if not link_path.is_absolute():
        link_path = Path.cwd() / link_path
    link_path = normalize_absolute_path(link_path)

    target_abs = resolve_user_target(target_path_raw)
    target_resolved = target_abs.resolve(strict=False)
    remote = is_remote_path(link_path) or is_remote_path(target_abs)

    if not no_validate_target and not target_abs.exists():
        typer.secho("Error: Target path does not exist.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_abs)
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

    if link_path == target_abs or link_path == target_resolved:
        typer.secho("Error: Link path and target path cannot be the same.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, target_abs)
        typer.echo("\nSpecify a different link name or location. Example:")
        typer.echo(f"  pylink {target_abs} {target_abs.parent / (target_abs.stem + '_link' + target_abs.suffix)}")
        raise typer.Exit(code=1)

    flag = ""
    if directory:
        flag = "/D"
    elif junction:
        flag = "/J"
    elif hard:
        flag = "/H"
    elif target_abs.exists() and target_abs.is_dir():
        flag = resolve_default_directory_flag(
            yes=yes,
            relative_target=relative_input or relative,
            remote=remote,
        )

    if flag == "/J":
        junc_err = junction_remote_error_message(link_path, target_abs)
        if junc_err:
            typer.secho(f"Error: {junc_err}", fg=typer.colors.RED, bold=True)
            raise typer.Exit(code=1)

    if flag in ("/J", "/H"):
        stored_target = str(target_abs)
        if flag == "/J" and relative_input:
            typer.secho(
                "Note: junctions always store an absolute target.",
                fg=typer.colors.YELLOW,
            )
    else:
        stored_target = stored_symlink_target(
            target_path_raw,
            link_path,
            force_relative=relative,
        )
        if relative and target_looks_nonportable(stored_target):
            typer.secho(
                "Warning: could not store a relative target (different drive). Using an absolute path.",
                fg=typer.colors.YELLOW,
            )

    if not no_validate_target and flag in ("/D", "/J") and not target_abs.is_dir():
        typer.secho("Error: Directory links require a directory target.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, stored_target, flag, resolved_target=target_abs)
        raise typer.Exit(code=1)
    if not no_validate_target and flag == "/H" and target_abs.is_dir():
        typer.secho("Error: Hard links only support file targets.", fg=typer.colors.RED, bold=True)
        show_link_context(link_path, stored_target, flag, resolved_target=target_abs)
        raise typer.Exit(code=1)

    _warn_nonportable_target(stored_target, flag)
    _warn_r2r_if_needed(link_path, flag)

    if not yes:
        show_link_context(link_path, stored_target, flag, resolved_target=target_abs)
        if not typer.confirm("Proceed?", default=True):
            typer.secho("Cancelled.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

    typer.secho("Executing:", fg=typer.colors.BLUE)
    try:
        detail = create_windows_link(link_path, stored_target, flag)
        typer.secho(f"  {detail}", fg=typer.colors.BLUE)
        typer.secho("Success!", fg=typer.colors.GREEN, bold=True)
        show_link_context(link_path, stored_target, flag, resolved_target=target_abs)
    except OSError as e:
        typer.secho("\n==============================", fg=typer.colors.RED)
        typer.secho("  FAILED TO CREATE LINK", fg=typer.colors.RED, bold=True)
        typer.secho("==============================\n", fg=typer.colors.RED)
        typer.secho(f"  {e}", fg=typer.colors.RED)
        typer.secho("\nPossible causes:", fg=typer.colors.YELLOW, bold=True)
        for hint in create_link_error_hints(
            e,
            flag=flag,
            remote=remote,
            stored_target=stored_target,
            link_path=link_path,
        ):
            typer.echo(f"  • {hint}")
        typer.echo(f"\n  pylink create-link {target_path_raw} {link_path}")
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
    relative: bool = typer.Option(
        False,
        "--relative",
        "-R",
        help="Store a target relative to the link parent (symlinks only; like ln -sr)",
    ),
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
        relative=relative,
        no_validate_target=no_validate_target,
    )


if __name__ == "__main__":
    app(_normalize_cli_argv())
