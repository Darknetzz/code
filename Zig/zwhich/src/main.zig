const std = @import("std");
const builtin = @import("builtin");
const Io = std.Io;
const zwhich = @import("zwhich");
const zcommon = @import("zcommon");

const ExistsCtx = struct {
    io: Io,
};

fn pathExists(ctx: *anyopaque, full_path: []const u8) bool {
    const self: *const ExistsCtx = @ptrCast(@alignCast(ctx));
    const st = Io.Dir.statFile(.cwd(), self.io, full_path, .{ .follow_symlinks = true }) catch return false;
    return st.kind != .directory;
}

fn writeHelp(w: *Io.Writer, c: zcommon.Color) !void {
    try w.print("{s}zwhich{s} — PATH lookup (every match, winner first)\n\n", .{ c.s(.bold), c.s(.reset) });
    try w.print("{s}Usage:{s}\n", .{ c.s(.bold), c.s(.reset) });
    try w.writeAll("  zwhich [OPTIONS] NAME [NAME...]\n\n");
    try w.print("{s}Options:{s}\n", .{ c.s(.bold), c.s(.reset) });
    try w.print("  {s}-1, --first{s}       Print only the winning path\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("      {s}--cwd{s}         Search the current directory first\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("      {s}--no-cwd{s}      Do not search cwd first\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("      {s}--path PATH{s}   Override PATH\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("      {s}--pathext EXT{s} Override PATHEXT (Windows)\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("  {s}-h, --help{s}\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("  {s}-V, --version{s}\n\n", .{ c.s(.cyan), c.s(.reset) });
}

pub fn main(init: std.process.Init) !void {
    const color = zcommon.setupTerminal(init.io, init.environ_map);
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
            try writeHelp(stdout, color);
            try stdout.flush();
            return;
        },
        error.UnknownFlag => {
            try stderr.print("{s}Error:{s} unknown option. See --help.\n", .{ color.s(.red), color.s(.reset) });
            try stderr.flush();
            std.process.exit(1);
        },
        error.MissingValue => {
            try stderr.print("{s}Error:{s} option requires a value.\n", .{ color.s(.red), color.s(.reset) });
            try stderr.flush();
            std.process.exit(1);
        },
        error.OutOfMemory => return error.OutOfMemory,
    };

    if (opts.help) {
        try writeHelp(stdout, color);
        try stdout.flush();
        return;
    }
    if (opts.version) {
        try stdout.print("{s}zwhich{s} {s}\n", .{ color.s(.bold), color.s(.reset), zwhich.version });
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
            try stderr.print("{s}zwhich: {s}: not found{s}\n", .{ color.s(.red), name, color.s(.reset) });
            missing = 1;
            continue;
        }

        if (opts.first_only) {
            try stdout.print("{s}{s}{s}\n", .{ color.s(.cyan), matches[0], color.s(.reset) });
            continue;
        }

        for (matches, 0..) |m, i| {
            if (i == 0) {
                try stdout.print("{s}*{s} {s}{s}{s}\n", .{ color.s(.green), color.s(.reset), color.s(.cyan), m, color.s(.reset) });
            } else {
                try stdout.print("  {s}{s}{s}\n", .{ color.s(.dim), m, color.s(.reset) });
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
