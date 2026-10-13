const std = @import("std");
const Io = std.Io;
const zgen = @import("zgen");
const zcommon = @import("zcommon");

fn writeHelp(w: *Io.Writer, c: zcommon.Color) !void {
    try w.print("{s}zgen{s} — generate random strings from a character set\n\n", .{ c.s(.bold), c.s(.reset) });
    try w.print("{s}Usage:{s}\n", .{ c.s(.bold), c.s(.reset) });
    try w.writeAll("  zgen [LENGTH] [OPTIONS]\n\n");
    try w.print("{s}Options:{s}\n", .{ c.s(.bold), c.s(.reset) });
    try w.print("  {s}-p, --preset NAME{s}   Character preset (default: alphanumeric)\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("  {s}-c, --charset STR{s}   Custom charset (overrides --preset)\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("  {s}-n, --count N{s}       Number of strings to print (default: 1)\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("      {s}--insecure{s}       Use a fast non-crypto PRNG\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("  {s}-h, --help{s}\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("  {s}-V, --version{s}\n\n", .{ c.s(.cyan), c.s(.reset) });
    try w.print("{s}Presets:{s}\n", .{ c.s(.bold), c.s(.reset) });
    for (zgen.presets) |p| {
        try w.print("  {s}{s}{s}\n", .{ c.s(.cyan), p.name, c.s(.reset) });
    }
    try w.print("\nDefault length is {d}. Each string is printed on its own line.\n", .{zgen.default_length});
}

fn printErr(stderr: *Io.Writer, color: zcommon.Color, comptime fmt: []const u8, args: anytype) !void {
    try stderr.print("{s}Error:{s} ", .{ color.s(.red), color.s(.reset) });
    try stderr.print(fmt, args);
    try stderr.writeAll("\n");
    try stderr.flush();
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

    const opts = zgen.parseArgs(args[1..]) catch |err| switch (err) {
        error.UnknownFlag => {
            try printErr(stderr, color, "unknown option. See --help.", .{});
            std.process.exit(1);
        },
        error.MissingValue => {
            try printErr(stderr, color, "option requires a value.", .{});
            std.process.exit(1);
        },
        error.InvalidLength => {
            try printErr(stderr, color, "length must be a positive integer.", .{});
            std.process.exit(1);
        },
        error.InvalidCount => {
            try printErr(stderr, color, "count must be a positive integer.", .{});
            std.process.exit(1);
        },
        error.UnexpectedPositional => {
            try printErr(stderr, color, "unexpected argument. See --help.", .{});
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
        try stdout.print("{s}zgen{s} {s}\n", .{ color.s(.bold), color.s(.reset), zgen.version });
        try stdout.flush();
        return;
    }

    const charset = zgen.resolveCharset(opts.preset, opts.charset) catch |err| switch (err) {
        error.InvalidPreset => {
            try printErr(stderr, color, "unknown preset '{s}'. See --help.", .{opts.preset});
            std.process.exit(1);
        },
        error.EmptyCharset => {
            try printErr(stderr, color, "charset must not be empty.", .{});
            std.process.exit(1);
        },
    };

    var secure_src: std.Random.IoSource = .{ .io = init.io };
    var prng: std.Random.DefaultPrng = undefined;
    const rng: std.Random = if (opts.insecure) blk: {
        var seed: [8]u8 = undefined;
        init.io.random(&seed);
        prng = .init(std.mem.readInt(u64, &seed, .little));
        break :blk prng.random();
    } else secure_src.interface();

    const buf = try arena.alloc(u8, opts.length);
    var i: usize = 0;
    while (i < opts.count) : (i += 1) {
        zgen.fillRandom(rng, charset, buf);
        try stdout.print("{s}\n", .{buf});
    }
    try stdout.flush();
}
