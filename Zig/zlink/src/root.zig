//! Pure helpers for zlink (Windows mklink-style CLI).
const std = @import("std");
const path = std.fs.path;

pub const version = "0.1.0";
pub const drive_remote: u32 = 4;

pub const known_subcommands = [_][]const u8{ "version", "info", "remove", "create-link" };

pub const LinkFlag = enum {
    file_symlink,
    dir_symlink,
    junction,
    hard,

    pub fn mklink(self: LinkFlag) []const u8 {
        return switch (self) {
            .file_symlink => "",
            .dir_symlink => "/D",
            .junction => "/J",
            .hard => "/H",
        };
    }

    pub fn fromMklink(flag: []const u8) ?LinkFlag {
        if (flag.len == 0) return .file_symlink;
        if (std.mem.eql(u8, flag, "/D")) return .dir_symlink;
        if (std.mem.eql(u8, flag, "/J")) return .junction;
        if (std.mem.eql(u8, flag, "/H")) return .hard;
        return null;
    }
};

pub fn formatLinkType(flag: []const u8) []const u8 {
    if (std.mem.eql(u8, flag, "/J")) return "/J (directory junction)";
    if (std.mem.eql(u8, flag, "/D")) return "/D (directory symbolic link)";
    if (std.mem.eql(u8, flag, "/H")) return "/H (hard link, same volume, files only)";
    if (flag.len == 0) return "file symbolic link";
    return flag;
}

pub fn formatLinkDisplay(allocator: std.mem.Allocator, link_path: []const u8, target_path: []const u8) ![]u8 {
    return std.fmt.allocPrint(allocator, "{s} -> {s}", .{ link_path, target_path });
}

pub fn isDriveRoot(p: []const u8) bool {
    const parsed = path.parsePathWindows(u8, p);
    if (parsed.kind != .drive_absolute) return false;
    var i: usize = parsed.root.len;
    while (i < p.len and path.isSep(p[i])) i += 1;
    return i == p.len;
}

pub fn userTargetIsRelative(target_raw: []const u8) bool {
    return !path.isAbsoluteWindows(target_raw);
}

pub fn isUncPath(p: []const u8) bool {
    if (p.len < 2) return false;
    var buf: [4096]u8 = undefined;
    if (p.len > buf.len) return false;
    @memcpy(buf[0..p.len], p);
    std.mem.replaceScalar(u8, buf[0..p.len], '/', '\\');
    const s = buf[0..p.len];
    if (startsWithIgnoreCase(s, "\\\\?\\UNC\\") or startsWithIgnoreCase(s, "\\??\\UNC\\")) return true;
    if (std.mem.startsWith(u8, s, "\\\\?\\") or std.mem.startsWith(u8, s, "\\??\\")) return false;
    return std.mem.startsWith(u8, s, "\\\\");
}

pub fn targetLooksNonportable(target: []const u8) bool {
    if (isUncPath(target)) return true;
    if (std.mem.startsWith(u8, target, "\\??\\") or std.mem.startsWith(u8, target, "\\\\?\\")) return true;
    const parsed = path.parsePathWindows(u8, target);
    return switch (parsed.kind) {
        .drive_absolute, .drive_relative => true,
        else => false,
    };
}

pub const DriveTypeFn = *const fn (root: []const u8) u32;

pub fn isRemotePath(p: []const u8, drive_type_fn: ?DriveTypeFn) bool {
    if (isUncPath(p)) return true;
    const root = driveRoot(p) orelse return false;
    const func = drive_type_fn orelse return false;
    return func(root) == drive_remote;
}

/// Returns a slice into `p` like `D:\` when the path has a drive letter.
pub fn driveRoot(p: []const u8) ?[]const u8 {
    var s = p;
    if (std.mem.startsWith(u8, s, "\\\\?\\") or std.mem.startsWith(u8, s, "\\??\\")) {
        s = s[4..];
        if (startsWithIgnoreCase(s, "UNC\\")) return null;
    }
    const parsed = path.parsePathWindows(u8, s);
    if (parsed.kind != .drive_absolute and parsed.kind != .drive_relative) return null;
    if (parsed.root.len >= 3) return parsed.root[0..3];
    if (parsed.root.len >= 2 and parsed.root[1] == ':') {
        // `D:` drive-relative — caller should treat as `D:\` via GetDriveTypeW.
        return parsed.root[0..2];
    }
    return null;
}

pub fn preferDirectorySymlink(relative_target: bool, remote: bool) bool {
    return relative_target or remote;
}

pub fn validateLinkFlags(directory: bool, junction: bool, hard: bool) ?[]const u8 {
    const n: u8 = @as(u8, @intFromBool(directory)) + @as(u8, @intFromBool(junction)) + @as(u8, @intFromBool(hard));
    if (n > 1) return "You cannot use --dir, --junction, and --hard simultaneously.";
    return null;
}

pub fn validateRelativeFlag(relative: bool, junction: bool, hard: bool) ?[]const u8 {
    if (relative and (junction or hard)) {
        return "--relative cannot be used with --junction or --hard (those APIs require an absolute target).";
    }
    return null;
}

pub fn resolveDefaultDirectoryFlag(yes: bool, relative_target: bool, remote: bool) []const u8 {
    if (preferDirectorySymlink(relative_target, remote)) return "/D";
    _ = yes;
    return "/J";
}

pub fn junctionRemoteErrorMessage(link_path: []const u8, target_path: []const u8, drive_type_fn: ?DriveTypeFn) ?[]const u8 {
    if (!(isRemotePath(link_path, drive_type_fn) or isRemotePath(target_path, drive_type_fn))) return null;
    return "Junctions require a local NTFS volume. This path is on a network share; use a directory symlink (--dir) with a relative target instead.";
}

pub fn posixLnSuggestion(allocator: std.mem.Allocator, stored_target: []const u8, link_path: []const u8) ![]u8 {
    var posix_target = stored_target;
    var owned: ?[]u8 = null;
    defer if (owned) |o| allocator.free(o);
    if (targetLooksNonportable(stored_target)) {
        posix_target = path.basename(stored_target);
    } else if (std.mem.indexOfScalar(u8, stored_target, '\\') != null) {
        const dup = try allocator.dupe(u8, stored_target);
        std.mem.replaceScalar(u8, dup, '\\', '/');
        owned = dup;
        posix_target = dup;
    }
    return std.fmt.allocPrint(allocator, "ln -s {s} {s}", .{ posix_target, path.basename(link_path) });
}

pub fn resolveUserTarget(allocator: std.mem.Allocator, cwd: []const u8, target_raw: []const u8) ![]u8 {
    if (path.isAbsoluteWindows(target_raw)) {
        return path.resolveAlloc(allocator, &.{target_raw});
    }
    return path.resolveAlloc(allocator, &.{ cwd, target_raw });
}

pub fn storedSymlinkTarget(
    allocator: std.mem.Allocator,
    cwd: []const u8,
    target_raw: []const u8,
    link_path: []const u8,
    force_relative: bool,
) ![]u8 {
    const resolved = try resolveUserTarget(allocator, cwd, target_raw);
    if (!(force_relative or userTargetIsRelative(target_raw))) {
        return resolved;
    }
    const parent = path.dirname(link_path) orelse link_path;
    const rel = try path.relativeAlloc(allocator, cwd, null, parent, resolved);
    allocator.free(resolved);
    std.mem.replaceScalar(u8, rel, '\\', '/');
    return rel;
}

pub fn normalizeCliArgv(allocator: std.mem.Allocator, argv: []const []const u8) ![][]const u8 {
    if (argv.len == 0) return allocator.dupe([]const u8, argv);
    const first = argv[0];
    if (std.mem.eql(u8, first, "--version") or std.mem.eql(u8, first, "-V")) {
        const out = try allocator.alloc([]const u8, 1);
        out[0] = "version";
        return out;
    }
    if (isKnownSubcommand(first) or isGroupOnlyFlag(first)) {
        return allocator.dupe([]const u8, argv);
    }
    const out = try allocator.alloc([]const u8, argv.len + 1);
    out[0] = "create-link";
    @memcpy(out[1..], argv);
    return out;
}

fn isKnownSubcommand(token: []const u8) bool {
    for (known_subcommands) |cmd| {
        if (std.mem.eql(u8, token, cmd)) return true;
    }
    return false;
}

fn isGroupOnlyFlag(token: []const u8) bool {
    return std.mem.eql(u8, token, "-h") or std.mem.eql(u8, token, "--help");
}

pub const CreateOptions = struct {
    target: []const u8,
    link: ?[]const u8 = null,
    directory: bool = false,
    junction: bool = false,
    hard: bool = false,
    yes: bool = false,
    replace: bool = false,
    relative: bool = false,
    no_validate_target: bool = false,
    help: bool = false,
};

pub const ParseError = error{ MissingTarget, UnknownFlag, ExtraArgs };

pub fn parseCreateArgs(args: []const []const u8) ParseError!CreateOptions {
    var opts: CreateOptions = .{ .target = "" };
    var positionals: [2][]const u8 = undefined;
    var n_pos: usize = 0;

    var i: usize = 0;
    while (i < args.len) : (i += 1) {
        const arg = args[i];
        if (std.mem.eql(u8, arg, "--dir") or std.mem.eql(u8, arg, "-d")) {
            opts.directory = true;
        } else if (std.mem.eql(u8, arg, "--junction") or std.mem.eql(u8, arg, "-j")) {
            opts.junction = true;
        } else if (std.mem.eql(u8, arg, "--hard") or std.mem.eql(u8, arg, "-H")) {
            opts.hard = true;
        } else if (std.mem.eql(u8, arg, "--yes") or std.mem.eql(u8, arg, "-y")) {
            opts.yes = true;
        } else if (std.mem.eql(u8, arg, "--replace") or std.mem.eql(u8, arg, "-r")) {
            opts.replace = true;
        } else if (std.mem.eql(u8, arg, "--relative") or std.mem.eql(u8, arg, "-R")) {
            opts.relative = true;
        } else if (std.mem.eql(u8, arg, "--no-validate-target")) {
            opts.no_validate_target = true;
        } else if (std.mem.eql(u8, arg, "--help") or std.mem.eql(u8, arg, "-h")) {
            opts.help = true;
        } else if (std.mem.startsWith(u8, arg, "-")) {
            return error.UnknownFlag;
        } else {
            if (n_pos >= positionals.len) return error.ExtraArgs;
            positionals[n_pos] = arg;
            n_pos += 1;
        }
    }

    if (opts.help) return opts;
    if (n_pos == 0) return error.MissingTarget;
    opts.target = positionals[0];
    if (n_pos >= 2) opts.link = positionals[1];
    return opts;
}

fn startsWithIgnoreCase(hay: []const u8, needle: []const u8) bool {
    if (hay.len < needle.len) return false;
    return std.ascii.eqlIgnoreCase(hay[0..needle.len], needle);
}

test "is_drive_root" {
    try std.testing.expect(isDriveRoot("D:\\"));
    try std.testing.expect(!isDriveRoot("D:\\folder"));
}

test "validate_link_flags_exclusive" {
    try std.testing.expect(validateLinkFlags(true, true, false) != null);
    try std.testing.expect(validateLinkFlags(false, false, false) == null);
}

test "validate_relative_flag" {
    try std.testing.expect(validateRelativeFlag(true, true, false) != null);
    try std.testing.expect(validateRelativeFlag(true, false, true) != null);
    try std.testing.expect(validateRelativeFlag(true, false, false) == null);
    try std.testing.expect(validateRelativeFlag(false, true, false) == null);
}

test "resolve_default_directory_flag_yes" {
    try std.testing.expectEqualStrings("/J", resolveDefaultDirectoryFlag(true, false, false));
    try std.testing.expectEqualStrings("/D", resolveDefaultDirectoryFlag(true, false, true));
    try std.testing.expectEqualStrings("/D", resolveDefaultDirectoryFlag(true, true, false));
}

test "prefer_directory_symlink" {
    try std.testing.expect(!preferDirectorySymlink(false, false));
    try std.testing.expect(preferDirectorySymlink(true, false));
    try std.testing.expect(preferDirectorySymlink(false, true));
}

test "format_link_display" {
    const line = try formatLinkDisplay(std.testing.allocator, "D:\\link", "C:\\target");
    defer std.testing.allocator.free(line);
    try std.testing.expectEqualStrings("D:\\link -> C:\\target", line);
}

test "format_link_type" {
    try std.testing.expectEqualStrings("/J (directory junction)", formatLinkType("/J"));
    try std.testing.expectEqualStrings("/D (directory symbolic link)", formatLinkType("/D"));
    try std.testing.expectEqualStrings("/H (hard link, same volume, files only)", formatLinkType("/H"));
    try std.testing.expectEqualStrings("file symbolic link", formatLinkType(""));
    try std.testing.expectEqualStrings("/X", formatLinkType("/X"));
}

test "normalize_cli_argv" {
    const a = std.testing.allocator;
    {
        const out = try normalizeCliArgv(a, &.{"version"});
        defer a.free(out);
        try std.testing.expectEqualStrings("version", out[0]);
    }
    {
        const out = try normalizeCliArgv(a, &.{"--version"});
        defer a.free(out);
        try std.testing.expectEqualStrings("version", out[0]);
    }
    {
        const out = try normalizeCliArgv(a, &.{ "-V", });
        defer a.free(out);
        try std.testing.expectEqualStrings("version", out[0]);
    }
    {
        const out = try normalizeCliArgv(a, &.{ "info", "D:\\link" });
        defer a.free(out);
        try std.testing.expectEqualStrings("info", out[0]);
    }
    {
        const out = try normalizeCliArgv(a, &.{"--help"});
        defer a.free(out);
        try std.testing.expectEqualStrings("--help", out[0]);
    }
    {
        const out = try normalizeCliArgv(a, &.{ "C:\\target", "D:\\link" });
        defer a.free(out);
        try std.testing.expectEqualStrings("create-link", out[0]);
        try std.testing.expectEqualStrings("C:\\target", out[1]);
    }
    {
        const out = try normalizeCliArgv(a, &.{ "-y", "C:\\target", "D:\\link" });
        defer a.free(out);
        try std.testing.expectEqualStrings("create-link", out[0]);
        try std.testing.expectEqualStrings("-y", out[1]);
    }
}

test "is_unc_path" {
    try std.testing.expect(isUncPath("\\\\nas3\\share\\foo"));
    try std.testing.expect(isUncPath("//nas3/share/foo"));
    try std.testing.expect(isUncPath("\\\\?\\UNC\\nas3\\share\\foo"));
    try std.testing.expect(!isUncPath("D:\\folder"));
    try std.testing.expect(!isUncPath("\\\\?\\D:\\folder"));
}

fn driveTypeRemote(_: []const u8) u32 {
    return 4;
}

fn driveTypeLocal(_: []const u8) u32 {
    return 3;
}

test "is_remote_path" {
    try std.testing.expect(isRemotePath("\\\\nas3\\share\\foo", null));
    try std.testing.expect(isRemotePath("Z:\\Code\\Web", driveTypeRemote));
    try std.testing.expect(!isRemotePath("D:\\local", driveTypeLocal));
}

test "target_looks_nonportable" {
    try std.testing.expect(targetLooksNonportable("Z:\\Code\\foo"));
    try std.testing.expect(targetLooksNonportable("\\\\nas3\\share\\foo"));
    try std.testing.expect(targetLooksNonportable("\\??\\Z:\\Code\\foo"));
    try std.testing.expect(!targetLooksNonportable("fullcalendar-7.0.2"));
    try std.testing.expect(!targetLooksNonportable("../other/foo"));
}

test "stored_symlink_target_same_dir" {
    const a = std.testing.allocator;
    const cwd = "C:\\assets";
    const stored = try storedSymlinkTarget(a, cwd, "fullcalendar-7.0.2", "C:\\assets\\latest", false);
    defer a.free(stored);
    try std.testing.expectEqualStrings("fullcalendar-7.0.2", stored);
}

test "stored_symlink_target_trailing_slash_and_dot_prefix" {
    const a = std.testing.allocator;
    const cwd = "C:\\assets";
    const slash = try storedSymlinkTarget(a, cwd, "fullcalendar-7.0.2\\", "C:\\assets\\latest", false);
    defer a.free(slash);
    const dot = try storedSymlinkTarget(a, cwd, ".\\fullcalendar-7.0.2", "C:\\assets\\latest", false);
    defer a.free(dot);
    try std.testing.expectEqualStrings("fullcalendar-7.0.2", slash);
    try std.testing.expectEqualStrings("fullcalendar-7.0.2", dot);
}

test "stored_symlink_target_cwd_differs" {
    const a = std.testing.allocator;
    const stored = try storedSymlinkTarget(
        a,
        "C:\\work",
        "fullcalendar\\fullcalendar-7.0.2",
        "C:\\work\\fullcalendar\\latest",
        false,
    );
    defer a.free(stored);
    try std.testing.expectEqualStrings("fullcalendar-7.0.2", stored);
}

test "stored_symlink_target_absolute_kept" {
    const a = std.testing.allocator;
    const stored = try storedSymlinkTarget(a, "C:\\assets", "C:\\assets\\fullcalendar-7.0.2", "C:\\assets\\latest", false);
    defer a.free(stored);
    try std.testing.expect(path.isAbsoluteWindows(stored));
    try std.testing.expectEqualStrings("C:\\assets\\fullcalendar-7.0.2", stored);
}

test "stored_symlink_target_force_relative" {
    const a = std.testing.allocator;
    const stored = try storedSymlinkTarget(a, "C:\\tmp", "C:\\tmp\\other\\foo", "C:\\tmp\\fullcalendar\\latest", true);
    defer a.free(stored);
    try std.testing.expectEqualStrings("../other/foo", stored);
    try std.testing.expect(std.mem.indexOfScalar(u8, stored, '\\') == null);
}

test "junction_remote_error_message" {
    try std.testing.expect(junctionRemoteErrorMessage("\\\\nas3\\share\\latest", "\\\\nas3\\share\\fullcalendar-7.0.2", null) != null);
    try std.testing.expect(junctionRemoteErrorMessage("D:\\latest", "D:\\target", driveTypeLocal) == null);
}

test "posix_ln_suggestion" {
    const line = try posixLnSuggestion(std.testing.allocator, "fullcalendar-7.0.2", "Z:\\assets\\latest");
    defer std.testing.allocator.free(line);
    try std.testing.expectEqualStrings("ln -s fullcalendar-7.0.2 latest", line);
}

test "parse_create_args" {
    const opts = try parseCreateArgs(&.{ "-y", "C:\\target", "D:\\link", "--dir" });
    try std.testing.expectEqualStrings("C:\\target", opts.target);
    try std.testing.expectEqualStrings("D:\\link", opts.link.?);
    try std.testing.expect(opts.yes);
    try std.testing.expect(opts.directory);
}
