const std = @import("std");

pub const version = "0.1.0";
pub const default_length: usize = 32;
pub const default_count: usize = 1;
pub const default_preset = "alphanumeric";

pub const Preset = struct {
    name: []const u8,
    chars: []const u8,
};

pub const presets = [_]Preset{
    .{ .name = "alphanumeric", .chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789" },
    .{ .name = "alphabetic", .chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" },
    .{ .name = "lowercase", .chars = "abcdefghijklmnopqrstuvwxyz" },
    .{ .name = "uppercase", .chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" },
    .{ .name = "numeric", .chars = "0123456789" },
    .{ .name = "hex", .chars = "0123456789abcdef" },
    .{ .name = "HEX", .chars = "0123456789ABCDEF" },
    .{ .name = "base64", .chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/" },
    .{ .name = "base64url", .chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" },
};

pub fn charsetForPreset(name: []const u8) ?[]const u8 {
    for (presets) |p| {
        if (std.mem.eql(u8, p.name, name)) return p.chars;
    }
    return null;
}

pub fn resolveCharset(preset_name: []const u8, custom: ?[]const u8) error{ InvalidPreset, EmptyCharset }![]const u8 {
    if (custom) |c| {
        if (c.len == 0) return error.EmptyCharset;
        return c;
    }
    return charsetForPreset(preset_name) orelse error.InvalidPreset;
}

pub fn fillRandom(rng: std.Random, charset: []const u8, buf: []u8) void {
    std.debug.assert(charset.len > 0);
    for (buf) |*c| {
        c.* = charset[rng.intRangeLessThan(usize, 0, charset.len)];
    }
}

pub const Options = struct {
    length: usize = default_length,
    count: usize = default_count,
    preset: []const u8 = default_preset,
    charset: ?[]const u8 = null,
    insecure: bool = false,
    help: bool = false,
    version: bool = false,
};

pub const ParseError = error{
    UnknownFlag,
    MissingValue,
    InvalidLength,
    InvalidCount,
    UnexpectedPositional,
    OutOfMemory,
};

fn takeValue(args: []const []const u8, i: *usize, inline_val: ?[]const u8) ParseError![]const u8 {
    if (inline_val) |v| return v;
    i.* += 1;
    if (i.* >= args.len) return error.MissingValue;
    return args[i.*];
}

fn parsePositive(s: []const u8) ?usize {
    const n = std.fmt.parseInt(usize, s, 10) catch return null;
    if (n == 0) return null;
    return n;
}

pub fn parseArgs(args: []const []const u8) ParseError!Options {
    var opts: Options = .{};
    var saw_length = false;

    var i: usize = 0;
    while (i < args.len) : (i += 1) {
        const arg = args[i];
        if (std.mem.eql(u8, arg, "-h") or std.mem.eql(u8, arg, "--help")) {
            opts.help = true;
        } else if (std.mem.eql(u8, arg, "-V") or std.mem.eql(u8, arg, "--version")) {
            opts.version = true;
        } else if (std.mem.eql(u8, arg, "--insecure")) {
            opts.insecure = true;
        } else if (std.mem.eql(u8, arg, "-p") or std.mem.eql(u8, arg, "--preset")) {
            opts.preset = try takeValue(args, &i, null);
        } else if (std.mem.startsWith(u8, arg, "--preset=")) {
            opts.preset = arg["--preset=".len..];
        } else if (std.mem.eql(u8, arg, "-c") or std.mem.eql(u8, arg, "--charset")) {
            opts.charset = try takeValue(args, &i, null);
        } else if (std.mem.startsWith(u8, arg, "--charset=")) {
            opts.charset = arg["--charset=".len..];
        } else if (std.mem.eql(u8, arg, "-n") or std.mem.eql(u8, arg, "--count")) {
            const v = try takeValue(args, &i, null);
            opts.count = parsePositive(v) orelse return error.InvalidCount;
        } else if (std.mem.startsWith(u8, arg, "--count=")) {
            opts.count = parsePositive(arg["--count=".len..]) orelse return error.InvalidCount;
        } else if (std.mem.startsWith(u8, arg, "-")) {
            return error.UnknownFlag;
        } else {
            if (saw_length) return error.UnexpectedPositional;
            opts.length = parsePositive(arg) orelse return error.InvalidLength;
            saw_length = true;
        }
    }

    return opts;
}

test "charsetForPreset covers named sets" {
    try std.testing.expectEqualStrings(
        "0123456789abcdef",
        charsetForPreset("hex").?,
    );
    try std.testing.expectEqualStrings(
        "0123456789ABCDEF",
        charsetForPreset("HEX").?,
    );
    try std.testing.expect(charsetForPreset("nope") == null);
}

test "resolveCharset prefers custom and rejects empty" {
    const custom = try resolveCharset("hex", "ABC");
    try std.testing.expectEqualStrings("ABC", custom);
    try std.testing.expectError(error.EmptyCharset, resolveCharset("hex", ""));
    try std.testing.expectError(error.InvalidPreset, resolveCharset("nope", null));
}

test "fillRandom stays within charset" {
    var prng = std.Random.DefaultPrng.init(0xC0FFEE);
    const rng = prng.random();
    const charset = "ABC";
    var buf: [64]u8 = undefined;
    fillRandom(rng, charset, &buf);
    for (buf) |c| {
        try std.testing.expect(std.mem.indexOfScalar(u8, charset, c) != null);
    }
}

test "parseArgs defaults and flags" {
    {
        const opts = try parseArgs(&.{});
        try std.testing.expectEqual(default_length, opts.length);
        try std.testing.expectEqual(default_count, opts.count);
        try std.testing.expectEqualStrings(default_preset, opts.preset);
        try std.testing.expect(!opts.insecure);
    }
    {
        const opts = try parseArgs(&.{ "48", "-p", "base64", "-n", "3", "--insecure" });
        try std.testing.expectEqual(@as(usize, 48), opts.length);
        try std.testing.expectEqual(@as(usize, 3), opts.count);
        try std.testing.expectEqualStrings("base64", opts.preset);
        try std.testing.expect(opts.insecure);
    }
    {
        const opts = try parseArgs(&.{ "--preset=hex", "--count=2", "--charset=xy" });
        try std.testing.expectEqualStrings("hex", opts.preset);
        try std.testing.expectEqual(@as(usize, 2), opts.count);
        try std.testing.expectEqualStrings("xy", opts.charset.?);
    }
    try std.testing.expectError(error.InvalidLength, parseArgs(&.{"0"}));
    try std.testing.expectError(error.InvalidCount, parseArgs(&.{ "--count", "0" }));
    try std.testing.expectError(error.UnknownFlag, parseArgs(&.{"--nope"}));
    try std.testing.expectError(error.UnexpectedPositional, parseArgs(&.{ "8", "16" }));
}
