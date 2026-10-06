const std = @import("std");

pub const default_name = "world";

pub fn formatGreeting(buf: []u8, name: []const u8) ![]u8 {
    return std.fmt.bufPrint(buf, "Hello, {s}!\n", .{name});
}

test "formatGreeting uses the given name" {
    var buf: [32]u8 = undefined;
    const line = try formatGreeting(&buf, "Zig");
    try std.testing.expectEqualStrings("Hello, Zig!\n", line);
}

test "formatGreeting default name" {
    var buf: [32]u8 = undefined;
    const line = try formatGreeting(&buf, default_name);
    try std.testing.expectEqualStrings("Hello, world!\n", line);
}
