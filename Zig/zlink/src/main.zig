const std = @import("std");
const builtin = @import("builtin");
const Io = std.Io;
const zlink = @import("zlink");
const zcommon = @import("zcommon");
const win32 = @import("win32.zig");

pub const usage =
    \\zlink — Windows symlink / junction / hardlink CLI (no cmd mklink)
    \\
    \\Usage:
    \\  zlink TARGET [LINK] [OPTIONS]
    \\  zlink info PATH
    \\  zlink remove PATH [-y]
    \\  zlink version
    \\
    \\Create options:
    \\  -d, --dir                 Directory symbolic link (/D)
    \\  -j, --junction            Directory junction (/J)
    \\  -H, --hard                Hard link (/H, files only)
    \\  -y, --yes                 Skip confirmation
    \\  -r, --replace             Replace existing LINK path
    \\  -R, --relative            Store a relative symlink target (like ln -sr)
    \\      --no-validate-target  Skip target existence/type checks
    \\
    \\If TARGET is a directory and no type flag is given, zlink defaults to a
    \\junction on local NTFS with an absolute target. Relative targets and
    \\network paths default to a directory symlink.
    \\
;

const App = struct {
    io: Io,
    arena: std.mem.Allocator,
    stdout: *Io.Writer,
    stderr: *Io.Writer,
    stdin: *Io.Reader,
};

pub fn main(init: std.process.Init) !void {
    zcommon.enableUtf8();
    if (builtin.os.tag != .windows) {
        std.debug.print("Error: zlink only supports Windows.\n", .{});
        return error.WindowsOnly;
    }

    const arena = init.arena.allocator();
    const args = try init.minimal.args.toSlice(arena);

    var stdout_buffer: [4096]u8 = undefined;
    var stdout_file = Io.File.Writer.init(.stdout(), init.io, &stdout_buffer);
    var stderr_buffer: [4096]u8 = undefined;
    var stderr_file = Io.File.Writer.init(.stderr(), init.io, &stderr_buffer);
    var stdin_buffer: [1024]u8 = undefined;
    var stdin_file = Io.File.Reader.initStreaming(.stdin(), init.io, &stdin_buffer);

    var app: App = .{
        .io = init.io,
        .arena = arena,
        .stdout = &stdout_file.interface,
        .stderr = &stderr_file.interface,
        .stdin = &stdin_file.interface,
    };

    const code = try dispatch(&app, args[1..]);
    try app.stdout.flush();
    try app.stderr.flush();
    if (code != 0) std.process.exit(code);
}

fn dispatch(app: *App, raw_args: []const []const u8) !u8 {
    const argv = try zlink.normalizeCliArgv(app.arena, raw_args);
    if (argv.len == 0 or std.mem.eql(u8, argv[0], "--help") or std.mem.eql(u8, argv[0], "-h")) {
        try app.stdout.writeAll(usage);
        return 0;
    }

    const cmd = argv[0];
    if (std.mem.eql(u8, cmd, "version")) {
        try app.stdout.print("zlink {s}\n", .{zlink.version});
        return 0;
    }
    if (std.mem.eql(u8, cmd, "info")) {
        if (argv.len < 2) {
            try printErr(app, "Error: info requires a path.", .{});
            return 1;
        }
        return infoCmd(app, argv[1]);
    }
    if (std.mem.eql(u8, cmd, "remove")) {
        var yes = false;
        var path_arg: ?[]const u8 = null;
        for (argv[1..]) |arg| {
            if (std.mem.eql(u8, arg, "-y") or std.mem.eql(u8, arg, "--yes")) {
                yes = true;
            } else if (std.mem.eql(u8, arg, "-h") or std.mem.eql(u8, arg, "--help")) {
                try app.stdout.writeAll("Usage: zlink remove PATH [-y]\n");
                return 0;
            } else if (path_arg == null) {
                path_arg = arg;
            }
        }
        if (path_arg == null) {
            try printErr(app, "Error: remove requires a path.", .{});
            return 1;
        }
        return removeCmd(app, path_arg.?, yes);
    }
    if (std.mem.eql(u8, cmd, "create-link")) {
        const opts = zlink.parseCreateArgs(argv[1..]) catch |err| switch (err) {
            error.MissingTarget => {
                try app.stdout.writeAll(usage);
                return 0;
            },
            error.UnknownFlag => {
                try printErr(app, "Error: unknown option. See --help.", .{});
                return 1;
            },
            error.ExtraArgs => {
                try printErr(app, "Error: too many arguments.", .{});
                return 1;
            },
        };
        if (opts.help) {
            try app.stdout.writeAll(usage);
            return 0;
        }
        return createCmd(app, opts);
    }

    try printErr(app, "Error: unknown command. See --help.", .{});
    return 1;
}

fn cwdPath(app: *App) ![]u8 {
    return std.process.currentPathAlloc(app.io, app.arena);
}

fn absPath(app: *App, raw: []const u8) ![]u8 {
    const cwd = try cwdPath(app);
    if (std.fs.path.isAbsoluteWindows(raw)) {
        return std.fs.path.resolveAlloc(app.arena, &.{raw});
    }
    return std.fs.path.resolveAlloc(app.arena, &.{ cwd, raw });
}

fn infoCmd(app: *App, raw: []const u8) !u8 {
    const link_path = try absPath(app, raw);
    const attrs = try win32.attributes(app.arena, link_path);
    if (attrs.missing()) {
        try printErr(app, "Path does not exist: {s}", .{link_path});
        return 1;
    }
    if (attrs.reparse()) {
        var buf: [Io.Dir.max_path_bytes]u8 = undefined;
        const n = Io.Dir.readLinkAbsolute(app.io, link_path, &buf) catch {
            try app.stdout.print("{s} -> (unavailable)\n", .{link_path});
            return 0;
        };
        const target = buf[0..n];
        try app.stdout.print("{s} -> {s}\n", .{ link_path, target });
        if (zlink.targetLooksNonportable(target)) {
            try printWarn(app, "Note: stored target is absolute (drive letter, UNC, or NT prefix); Linux will not follow this path.", .{});
        } else {
            try app.stdout.writeAll("Stored target is relative (portable across Windows and Linux).\n");
        }
    } else {
        try app.stdout.print("Path: {s} (not a link)\n", .{link_path});
    }
    return 0;
}

fn removeCmd(app: *App, raw: []const u8, yes: bool) !u8 {
    const link_path = try absPath(app, raw);
    const attrs = try win32.attributes(app.arena, link_path);
    if (attrs.missing()) {
        try printErr(app, "Path does not exist: {s}", .{link_path});
        return 1;
    }
    if (!attrs.reparse()) {
        try printErr(app, "Error: Path is not a link/junction.", .{});
        return 1;
    }
    if (zlink.isDriveRoot(link_path)) {
        try printErr(app, "Error: Refusing to remove a drive root.", .{});
        return 1;
    }
    if (!yes) {
        const ok = try confirm(app, "Remove link at {s}?", .{link_path}, false);
        if (!ok) {
            try printWarn(app, "Cancelled.", .{});
            return 0;
        }
    }
    deleteLinkPath(app, link_path, attrs) catch |err| {
        try printErr(app, "Error: {s}", .{@errorName(err)});
        return 1;
    };
    try printOk(app, "Removed.", .{});
    return 0;
}

fn deleteLinkPath(app: *App, link_path: []const u8, attrs: win32.Attrs) !void {
    if (attrs.directory()) {
        try Io.Dir.deleteDirAbsolute(app.io, link_path);
    } else {
        try Io.Dir.deleteFileAbsolute(app.io, link_path);
    }
}

fn createCmd(app: *App, opts: zlink.CreateOptions) !u8 {
    if (zlink.validateLinkFlags(opts.directory, opts.junction, opts.hard)) |msg| {
        try printErr(app, "Error: {s}", .{msg});
        return 1;
    }
    if (zlink.validateRelativeFlag(opts.relative, opts.junction, opts.hard)) |msg| {
        try printErr(app, "Error: {s}", .{msg});
        return 1;
    }

    const cwd = try cwdPath(app);
    const relative_input = zlink.userTargetIsRelative(opts.target);
    const link_raw = opts.link orelse std.fs.path.basename(opts.target);
    const link_path = try absPath(app, link_raw);
    const target_abs = try zlink.resolveUserTarget(app.arena, cwd, opts.target);
    const remote = win32.isRemotePath(app.arena, link_path) or win32.isRemotePath(app.arena, target_abs);

    const target_attrs = try win32.attributes(app.arena, target_abs);
    if (!opts.no_validate_target and target_attrs.missing()) {
        try printErr(app, "Error: Target path does not exist.", .{});
        try app.stderr.print("{s} -> {s}\n", .{ link_path, target_abs });
        return 1;
    }

    const link_attrs = try win32.attributes(app.arena, link_path);
    if (!link_attrs.missing()) {
        if (!opts.replace) {
            try printErr(app, "Error: Link path already exists.", .{});
            try printErr(app, "  Existing: {s}", .{link_path});
            try app.stderr.writeAll("Use --replace to remove and recreate the destination path.\n");
            return 1;
        }
        if (zlink.isDriveRoot(link_path)) {
            try printErr(app, "Error: Refusing to replace a drive root path.", .{});
            return 1;
        }
        const existing_is_link = link_attrs.reparse();
        if (opts.yes and !existing_is_link) {
            try printErr(app, "Error: Refusing non-interactive deletion of a real file/folder.", .{});
            try printErr(app, "Run again without --yes to complete interactive safety confirmation.", .{});
            return 1;
        }
        if (!opts.yes) {
            if (existing_is_link) {
                if (!try confirm(app, "'{s}' already exists as a link/junction. Remove and recreate it?", .{link_path}, false)) {
                    try printWarn(app, "Cancelled.", .{});
                    return 0;
                }
            } else {
                try printWarn(app, "WARNING: Existing destination is a real file/folder (not a link).", .{});
                try printWarn(app, "This will permanently delete it before creating the new link.", .{});
                if (!try confirm(app, "Confirm deletion of existing destination?", .{}, false)) {
                    try printWarn(app, "Cancelled.", .{});
                    return 0;
                }
                if (!try confirm(app, "Are you absolutely sure?", .{}, false)) {
                    try printWarn(app, "Cancelled.", .{});
                    return 0;
                }
                try app.stderr.writeAll("Type the full destination path exactly to continue: ");
                try app.stderr.flush();
                const typed = readLine(app) catch {
                    try printWarn(app, "Cancelled: typed path did not match.", .{});
                    return 0;
                };
                if (!std.mem.eql(u8, std.mem.trim(u8, typed, " \t\r\n"), link_path)) {
                    try printWarn(app, "Cancelled: typed path did not match.", .{});
                    return 0;
                }
            }
        }
        if (link_attrs.directory()) {
            if (existing_is_link) {
                Io.Dir.deleteDirAbsolute(app.io, link_path) catch |err| {
                    try printErr(app, "Error: Could not remove existing link path.", .{});
                    try printErr(app, "  {s}", .{@errorName(err)});
                    return 1;
                };
            } else {
                Io.Dir.deleteTree(.cwd(), app.io, link_path) catch |err| {
                    try printErr(app, "Error: Could not remove existing link path.", .{});
                    try printErr(app, "  {s}", .{@errorName(err)});
                    return 1;
                };
            }
        } else {
            Io.Dir.deleteFileAbsolute(app.io, link_path) catch |err| {
                try printErr(app, "Error: Could not remove existing link path.", .{});
                try printErr(app, "  {s}", .{@errorName(err)});
                return 1;
            };
        }
    }

    if (std.os.windows.eqlIgnoreCaseWtf8(link_path, target_abs)) {
        try printErr(app, "Error: Link path and target path cannot be the same.", .{});
        try app.stderr.print("{s} -> {s}\n", .{ link_path, target_abs });
        return 1;
    }

    var flag = zlink.LinkFlag.file_symlink;
    if (opts.directory) {
        flag = .dir_symlink;
    } else if (opts.junction) {
        flag = .junction;
    } else if (opts.hard) {
        flag = .hard;
    } else if (!target_attrs.missing() and target_attrs.directory()) {
        if (!opts.yes) {
            if (remote) {
                try printWarn(app, "This path is on a network share. Junctions require local NTFS.", .{});
            }
            if (relative_input or opts.relative) {
                try printWarn(app, "Target is relative. Junctions always store an absolute path, which breaks Linux consumers.", .{});
            }
            const default_choice: u8 = if (zlink.preferDirectorySymlink(relative_input or opts.relative, remote)) 'D' else 'J';
            try app.stderr.print(
                "Directory target detected. Choose link type: [J]unction or [D]irectory symlink [{c}]: ",
                .{default_choice},
            );
            try app.stderr.flush();
            const line = readLine(app) catch "";
            const trimmed = std.mem.trim(u8, line, " \t\r\n");
            if (trimmed.len == 0) {
                flag = zlink.LinkFlag.fromMklink(zlink.resolveDefaultDirectoryFlag(true, relative_input or opts.relative, remote)).?;
            } else {
                const c = std.ascii.toUpper(trimmed[0]);
                flag = if (c == 'D') .dir_symlink else if (c == 'J') .junction else zlink.LinkFlag.fromMklink(zlink.resolveDefaultDirectoryFlag(true, relative_input or opts.relative, remote)).?;
            }
        } else {
            flag = zlink.LinkFlag.fromMklink(zlink.resolveDefaultDirectoryFlag(true, relative_input or opts.relative, remote)).?;
        }
    }

    if (flag == .junction) {
        if (zlink.junctionRemoteErrorMessage(link_path, target_abs, if (remote) zlinkDriveRemote else zlinkDriveLocal)) |msg| {
            try printErr(app, "Error: {s}", .{msg});
            return 1;
        }
    }

    var stored_target: []const u8 = target_abs;
    if (flag == .junction or flag == .hard) {
        if (flag == .junction and relative_input) {
            try printWarn(app, "Note: junctions always store an absolute target.", .{});
        }
    } else {
        stored_target = try zlink.storedSymlinkTarget(app.arena, cwd, opts.target, link_path, opts.relative);
        if (opts.relative and zlink.targetLooksNonportable(stored_target)) {
            try printWarn(app, "Warning: could not store a relative target (different drive). Using an absolute path.", .{});
        }
    }

    if (!opts.no_validate_target and (flag == .dir_symlink or flag == .junction) and !target_attrs.directory()) {
        try printErr(app, "Error: Directory links require a directory target.", .{});
        return 1;
    }
    if (!opts.no_validate_target and flag == .hard and target_attrs.directory()) {
        try printErr(app, "Error: Hard links only support file targets.", .{});
        return 1;
    }

    if (flag != .junction and flag != .hard and zlink.targetLooksNonportable(stored_target)) {
        try printWarn(app, "Warning: stored target is absolute (drive letter or UNC). Linux will not follow this link.", .{});
    }
    if (flag != .junction and flag != .hard and win32.isRemotePath(app.arena, link_path)) {
        try printWarn(app, "Warning: Windows will not follow a remote-to-remote symlink until R2R is enabled:", .{});
        try app.stderr.writeAll("  fsutil behavior set SymlinkEvaluation R2R:1\n");
        try app.stderr.writeAll("Linux/Samba may still follow a POSIX symlink created on the server.\n");
    }

    if (!opts.yes) {
        try app.stderr.print("{s} -> {s}\n", .{ link_path, stored_target });
        if (!std.mem.eql(u8, stored_target, target_abs)) {
            try app.stderr.print("Resolves to: {s}\n", .{target_abs});
        }
        try app.stderr.print("Type:   {s}\n", .{zlink.formatLinkType(flag.mklink())});
        if (!try confirm(app, "Proceed?", .{}, true)) {
            try printWarn(app, "Cancelled.", .{});
            return 0;
        }
    }

    try app.stderr.writeAll("Executing:\n");
    const detail = createWindowsLink(app, link_path, stored_target, flag) catch |err| {
        const winerr = win32.lastError();
        try printErr(app, "FAILED TO CREATE LINK", .{});
        try printErr(app, "{s}", .{@errorName(err)});
        try app.stderr.writeAll("\nPossible causes:\n");
        try app.stderr.writeAll("  - The link path already exists. Remove it and retry.\n");
        try app.stderr.writeAll("  - Insufficient privileges. For symlinks, run as Administrator or enable Developer Mode.\n");
        if (winerr == win32.ERROR_PRIVILEGE_NOT_HELD) {
            try app.stderr.writeAll("  - WinError 1314: a required privilege is not held (enable Developer Mode or run elevated).\n");
        }
        if (flag == .junction) {
            try app.stderr.writeAll("  - Junctions require a local NTFS volume. They cannot be created on a mapped/UNC share.\n");
        }
        if (flag == .hard) {
            try app.stderr.writeAll("  - Hard links only work within the same volume.\n");
        }
        if (flag == .dir_symlink) {
            try app.stderr.writeAll("  - Directory symlinks require a directory target and appropriate privileges.\n");
        }
        if (remote) {
            try app.stderr.writeAll("  - The NAS/SMB server may not support Windows reparse points.\n");
            const ln = try zlink.posixLnSuggestion(app.arena, stored_target, link_path);
            try app.stderr.print("  - From Linux, create a POSIX symlink instead: {s}\n", .{ln});
        }
        return 1;
    };
    try app.stderr.print("  {s}\n", .{detail});
    try printOk(app, "Success!", .{});
    try app.stdout.print("{s} -> {s}\n", .{ link_path, stored_target });
    try app.stdout.print("Type:   {s}\n", .{zlink.formatLinkType(flag.mklink())});
    return 0;
}

fn zlinkDriveRemote(_: []const u8) u32 {
    return zlink.drive_remote;
}

fn zlinkDriveLocal(_: []const u8) u32 {
    return 3;
}

fn createWindowsLink(app: *App, link_path: []const u8, stored_target: []const u8, flag: zlink.LinkFlag) ![]u8 {
    const io = app.io;
    switch (flag) {
        .hard => {
            try Io.Dir.hardLink(.cwd(), stored_target, .cwd(), link_path, io, .{});
            return std.fmt.allocPrint(app.arena, "hardLink({s}, {s})", .{ stored_target, link_path });
        },
        .junction => {
            try win32.createJunction(app.arena, link_path, stored_target);
            return std.fmt.allocPrint(app.arena, "CreateJunction({s}, {s})", .{ stored_target, link_path });
        },
        .dir_symlink => {
            try Io.Dir.symLink(.cwd(), io, stored_target, link_path, .{ .is_directory = true });
            return std.fmt.allocPrint(app.arena, "symLink({s}, {s}, directory)", .{ stored_target, link_path });
        },
        .file_symlink => {
            try Io.Dir.symLink(.cwd(), io, stored_target, link_path, .{ .is_directory = false });
            return std.fmt.allocPrint(app.arena, "symLink({s}, {s})", .{ stored_target, link_path });
        },
    }
}

fn readLine(app: *App) ![]u8 {
    const line = app.stdin.takeDelimiterExclusive('\n') catch |err| switch (err) {
        error.EndOfStream => return app.arena.dupe(u8, ""),
        else => return err,
    };
    return app.arena.dupe(u8, std.mem.trim(u8, line, " \t\r\n"));
}

fn confirm(app: *App, comptime fmt: []const u8, args: anytype, default_yes: bool) !bool {
    try app.stderr.print(fmt, args);
    if (default_yes) {
        try app.stderr.writeAll(" [Y/n]: ");
    } else {
        try app.stderr.writeAll(" [y/N]: ");
    }
    try app.stderr.flush();
    const line = readLine(app) catch return default_yes;
    if (line.len == 0) return default_yes;
    const c = std.ascii.toLower(line[0]);
    if (c == 'y') return true;
    if (c == 'n') return false;
    return default_yes;
}

fn printErr(app: *App, comptime fmt: []const u8, args: anytype) !void {
    try app.stderr.print(fmt ++ "\n", args);
}

fn printWarn(app: *App, comptime fmt: []const u8, args: anytype) !void {
    try app.stderr.print(fmt ++ "\n", args);
}

fn printOk(app: *App, comptime fmt: []const u8, args: anytype) !void {
    try app.stderr.print(fmt ++ "\n", args);
}
