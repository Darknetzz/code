const std = @import("std");
const path = std.fs.path;

pub const version = "0.1.0";
pub const default_pathext = ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.MSC";

pub fn splitList(allocator: std.mem.Allocator, value: []const u8, delimiter: u8) ![][]const u8 {
    var list: std.ArrayList([]const u8) = .empty;
    errdefer list.deinit(allocator);

    var it = std.mem.splitScalar(u8, value, delimiter);
    while (it.next()) |raw| {
        const trimmed = std.mem.trim(u8, raw, " \t");
        const unquoted = unquote(trimmed);
        if (unquoted.len == 0) continue;
        try list.append(allocator, unquoted);
    }
    return list.toOwnedSlice(allocator);
}

fn unquote(s: []const u8) []const u8 {
    if (s.len >= 2 and ((s[0] == '"' and s[s.len - 1] == '"') or (s[0] == '\'' and s[s.len - 1] == '\''))) {
        return s[1 .. s.len - 1];
    }
    return s;
}

pub fn containsPathSep(name: []const u8) bool {
    return std.mem.indexOfScalar(u8, name, '/') != null or std.mem.indexOfScalar(u8, name, '\\') != null;
}

/// Windows CreateProcess: a name "has an extension" if the basename contains a dot.
pub fn hasExplicitExtension(name: []const u8) bool {
    const base = path.basename(name);
    return std.mem.indexOfScalar(u8, base, '.') != null;
}

pub fn candidateNames(allocator: std.mem.Allocator, name: []const u8, pathext: []const []const u8) ![][]const u8 {
    const base = path.basename(name);
    var list: std.ArrayList([]const u8) = .empty;
    errdefer list.deinit(allocator);

    try list.append(allocator, try allocator.dupe(u8, base));
    if (hasExplicitExtension(base) or pathext.len == 0) {
        return list.toOwnedSlice(allocator);
    }

    for (pathext) |ext_raw| {
        const ext = std.mem.trim(u8, ext_raw, " \t");
        if (ext.len == 0) continue;
        const cand = if (ext[0] == '.')
            try std.fmt.allocPrint(allocator, "{s}{s}", .{ base, ext })
        else
            try std.fmt.allocPrint(allocator, "{s}.{s}", .{ base, ext });
        for (cand[base.len..]) |*c| {
            c.* = std.ascii.toLower(c.*);
        }
        try list.append(allocator, cand);
    }
    return list.toOwnedSlice(allocator);
}

pub const ExistsFn = *const fn (ctx: *anyopaque, full_path: []const u8) bool;

pub fn alreadySeen(seen: []const []const u8, full_path: []const u8, ignore_case: bool) bool {
    for (seen) |prev| {
        if (ignore_case) {
            if (std.ascii.eqlIgnoreCase(prev, full_path)) return true;
        } else if (std.mem.eql(u8, prev, full_path)) {
            return true;
        }
    }
    return false;
}

pub fn findMatches(
    allocator: std.mem.Allocator,
    name: []const u8,
    dirs: []const []const u8,
    pathext: []const []const u8,
    ignore_case: bool,
    exists: ExistsFn,
    ctx: *anyopaque,
) ![][]u8 {
    const candidates = try candidateNames(allocator, name, pathext);
    defer {
        for (candidates) |c| allocator.free(c);
        allocator.free(candidates);
    }

    var matches: std.ArrayList([]u8) = .empty;
    errdefer {
        for (matches.items) |m| allocator.free(m);
        matches.deinit(allocator);
    }

    for (dirs) |dir| {
        for (candidates) |cand| {
            const full = try path.join(allocator, &.{ dir, cand });
            if (!exists(ctx, full)) {
                allocator.free(full);
                continue;
            }
            if (alreadySeen(matches.items, full, ignore_case)) {
                allocator.free(full);
                continue;
            }
            try matches.append(allocator, full);
        }
    }
    return matches.toOwnedSlice(allocator);
}

pub const Options = struct {
    first_only: bool = false,
    include_cwd: bool = false,
    include_cwd_set: bool = false,
    path_override: ?[]const u8 = null,
    pathext_override: ?[]const u8 = null,
    help: bool = false,
    version: bool = false,
    names: []const []const u8 = &.{},
};

pub const ParseError = error{ MissingName, UnknownFlag, MissingValue, OutOfMemory };

pub fn parseArgs(allocator: std.mem.Allocator, args: []const []const u8) ParseError!Options {
    var opts: Options = .{};
    var names: std.ArrayList([]const u8) = .empty;
    errdefer names.deinit(allocator);

    var i: usize = 0;
    while (i < args.len) : (i += 1) {
        const arg = args[i];
        if (std.mem.eql(u8, arg, "-h") or std.mem.eql(u8, arg, "--help")) {
            opts.help = true;
        } else if (std.mem.eql(u8, arg, "-V") or std.mem.eql(u8, arg, "--version")) {
            opts.version = true;
        } else if (std.mem.eql(u8, arg, "-1") or std.mem.eql(u8, arg, "--first")) {
            opts.first_only = true;
        } else if (std.mem.eql(u8, arg, "--no-cwd")) {
            opts.include_cwd = false;
            opts.include_cwd_set = true;
        } else if (std.mem.eql(u8, arg, "--cwd")) {
            opts.include_cwd = true;
            opts.include_cwd_set = true;
        } else if (std.mem.eql(u8, arg, "--path")) {
            i += 1;
            if (i >= args.len) return error.MissingValue;
            opts.path_override = args[i];
        } else if (std.mem.startsWith(u8, arg, "--path=")) {
            opts.path_override = arg["--path=".len..];
        } else if (std.mem.eql(u8, arg, "--pathext")) {
            i += 1;
            if (i >= args.len) return error.MissingValue;
            opts.pathext_override = args[i];
        } else if (std.mem.startsWith(u8, arg, "--pathext=")) {
            opts.pathext_override = arg["--pathext=".len..];
        } else if (std.mem.startsWith(u8, arg, "-")) {
            return error.UnknownFlag;
        } else {
            try names.append(allocator, arg);
        }
    }

    if (!opts.help and !opts.version and names.items.len == 0) return error.MissingName;
    opts.names = try names.toOwnedSlice(allocator);
    return opts;
}

test "splitList skips empties and quotes" {
    const a = std.testing.allocator;
    const parts = try splitList(a, "C:\\Bin;\"D:\\Tools\";;E:\\More", ';');
    defer a.free(parts);
    try std.testing.expectEqual(@as(usize, 3), parts.len);
    try std.testing.expectEqualStrings("C:\\Bin", parts[0]);
    try std.testing.expectEqualStrings("D:\\Tools", parts[1]);
    try std.testing.expectEqualStrings("E:\\More", parts[2]);
}

test "hasExplicitExtension" {
    try std.testing.expect(hasExplicitExtension("git.exe"));
    try std.testing.expect(hasExplicitExtension("C:\\foo\\python3.12"));
    try std.testing.expect(!hasExplicitExtension("git"));
    try std.testing.expect(!hasExplicitExtension("C:\\foo\\git"));
}

test "candidateNames appends PATHEXT" {
    const a = std.testing.allocator;
    const names = try candidateNames(a, "git", &.{ ".EXE", ".CMD" });
    defer {
        for (names) |n| a.free(n);
        a.free(names);
    }
    try std.testing.expectEqual(@as(usize, 3), names.len);
    try std.testing.expectEqualStrings("git", names[0]);
    try std.testing.expectEqualStrings("git.exe", names[1]);
    try std.testing.expectEqualStrings("git.cmd", names[2]);
}

test "candidateNames keeps explicit extension" {
    const a = std.testing.allocator;
    const names = try candidateNames(a, "git.exe", &.{".EXE"});
    defer {
        for (names) |n| a.free(n);
        a.free(names);
    }
    try std.testing.expectEqual(@as(usize, 1), names.len);
    try std.testing.expectEqualStrings("git.exe", names[0]);
}

const FakeFs = struct {
    files: []const []const u8,

    fn exists(ctx: *anyopaque, full: []const u8) bool {
        const self: *const FakeFs = @ptrCast(@alignCast(ctx));
        for (self.files) |f| {
            if (std.ascii.eqlIgnoreCase(f, full)) return true;
        }
        return false;
    }
};

test "findMatches orders PATHEXT then later PATH dirs" {
    const a = std.testing.allocator;
    var fs: FakeFs = .{
        .files = &.{
            "C:\\second\\git.exe",
            "C:\\first\\git.cmd",
            "C:\\first\\git.exe",
        },
    };
    const matches = try findMatches(
        a,
        "git",
        &.{ "C:\\first", "C:\\second" },
        &.{ ".EXE", ".CMD" },
        true,
        FakeFs.exists,
        @ptrCast(&fs),
    );
    defer {
        for (matches) |m| a.free(m);
        a.free(matches);
    }
    try std.testing.expectEqual(@as(usize, 3), matches.len);
    try std.testing.expectEqualStrings("C:\\first\\git.exe", matches[0]);
    try std.testing.expectEqualStrings("C:\\first\\git.cmd", matches[1]);
    try std.testing.expectEqualStrings("C:\\second\\git.exe", matches[2]);
}

test "parseArgs" {
    const a = std.testing.allocator;
    const opts = try parseArgs(a, &.{ "--first", "git", "--path", "C:\\Bin" });
    defer a.free(opts.names);
    try std.testing.expect(opts.first_only);
    try std.testing.expectEqualStrings("git", opts.names[0]);
    try std.testing.expectEqualStrings("C:\\Bin", opts.path_override.?);
}
