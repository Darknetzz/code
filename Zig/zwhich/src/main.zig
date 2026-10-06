const std = @import("std");
const builtin = @import("builtin");
const Io = std.Io;
const zwhich = @import("zwhich");

pub const usage =
    \\zwhich — PATH lookup (every match, winner first)
    \\
    \\Usage:
    \\  zwhich [OPTIONS] NAME [NAME...]
    \\
    \\Options:
    \\  -1, --first       Print only the winning path
    \\      --cwd         Search the current directory first
    \\      --no-cwd      Do not search cwd first
    \\      --path PATH   Override PATH
    \\      --pathext EXT Override PATHEXT (Windows)
    \\  -h, --help
    \\  -V, --version
    \\
;

const ExistsCtx = struct {
    io: Io,
};

fn pathExists(ctx: *anyopaque, full_path: []const u8) bool {
    const self: *const ExistsCtx = @ptrCast(@alignCast(ctx));
    const st = Io.Dir.statFile(.cwd(), self.io, full_path, .{ .follow_symlinks = true }) catch return false;
    return st.kind != .directory;
}

pub fn main(init: std.process.Init) !void {
    const arena = init.arena.allocator();
    const args = try init.minimal.args.toSlice(arena);

    var stdout_buffer: [4096]u8 = undefined;
    var stdout_file = Io.File.Writer.init(.stdout(), init.io, &stdout_buffer);
    const stdout = &stdout_file.interface;
    var stderr_buffer: [1024]u8 = undefined;
    var stderr_file = Io.File.Writer.init(.stderr(), init.io, &stderr_buffer);
    const stderr = &stderr_file.interface;

    const opts = zwhich.parseArgs(arena, args[1..]) catch |err| switch (err) {
        error.MissingName => {
            try stdout.writeAll(usage);
            try stdout.flush();
            return;
        },
        error.UnknownFlag => {
            try stderr.writeAll("Error: unknown option. See --help.\n");
            try stderr.flush();
            std.process.exit(1);
        },
        error.MissingValue => {
            try stderr.writeAll("Error: option requires a value.\n");
            try stderr.flush();
            std.process.exit(1);
        },
        error.OutOfMemory => return error.OutOfMemory,
    };

    if (opts.help) {
        try stdout.writeAll(usage);
        try stdout.flush();
        return;
    }
    if (opts.version) {
        try stdout.print("zwhich {s}\n", .{zwhich.version});
        try stdout.flush();
        return;
    }

    const include_cwd = if (opts.include_cwd_set) opts.include_cwd else (builtin.os.tag == .windows);
    const path_delim: u8 = if (builtin.os.tag == .windows) ';' else ':';
    const ignore_case = builtin.os.tag == .windows;

    const path_value = opts.path_override orelse init.environ_map.get("PATH") orelse "";
    const pathext_value = opts.pathext_override orelse init.environ_map.get("PATHEXT") orelse
        (if (builtin.os.tag == .windows) zwhich.default_pathext else "");

    const path_dirs = try zwhich.splitList(arena, path_value, path_delim);
    const pathext = if (pathext_value.len == 0)
        try arena.dupe([]const u8, &.{})
    else
        try zwhich.splitList(arena, pathext_value, ';');

    var exists_ctx: ExistsCtx = .{ .io = init.io };
    var missing: u8 = 0;

    for (opts.names) |name| {
        const dirs = try buildSearchDirs(arena, init.io, name, path_dirs, include_cwd);
        const matches = try zwhich.findMatches(
            arena,
            name,
            dirs,
            pathext,
            ignore_case,
            pathExists,
            @ptrCast(&exists_ctx),
        );

        if (matches.len == 0) {
            try stderr.print("zwhich: {s}: not found\n", .{name});
            missing = 1;
            continue;
        }

        if (opts.first_only) {
            try stdout.print("{s}\n", .{matches[0]});
            continue;
        }

        for (matches, 0..) |m, i| {
            if (i == 0) {
                try stdout.print("* {s}\n", .{m});
            } else {
                try stdout.print("  {s}\n", .{m});
            }
        }
    }

    try stdout.flush();
    try stderr.flush();
    if (missing != 0) std.process.exit(missing);
}

const path = std.fs.path;

fn buildSearchDirs(
    arena: std.mem.Allocator,
    io: Io,
    name: []const u8,
    path_dirs: []const []const u8,
    include_cwd: bool,
) ![][]const u8 {
    if (zwhich.containsPathSep(name)) {
        if (path.isAbsolute(name)) {
            const dir = path.dirname(name) orelse name;
            const one = try arena.alloc([]const u8, 1);
            one[0] = dir;
            return one;
        }
        const cwd = try std.process.currentPathAlloc(io, arena);
        const joined = try path.resolveAlloc(arena, &.{ cwd, name });
        const dir = path.dirname(joined) orelse cwd;
        const one = try arena.alloc([]const u8, 1);
        one[0] = dir;
        return one;
    }

    var dirs: std.ArrayList([]const u8) = .empty;
    if (include_cwd) {
        try dirs.append(arena, try std.process.currentPathAlloc(io, arena));
    }
    try dirs.appendSlice(arena, path_dirs);
    return dirs.toOwnedSlice(arena);
}
