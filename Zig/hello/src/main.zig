const std = @import("std");
const Io = std.Io;
const hello = @import("hello");
const zcommon = @import("zcommon");

pub fn main(init: std.process.Init) !void {
    zcommon.enableUtf8();
    const arena = init.arena.allocator();
    const args = try init.minimal.args.toSlice(arena);

    if (args.len >= 2 and isHelp(args[1])) {
        try writeUsage(init.io);
        return;
    }

    const name = if (args.len >= 2) args[1] else hello.default_name;

    var stdout_buffer: [1024]u8 = undefined;
    var stdout_file_writer: Io.File.Writer = .init(.stdout(), init.io, &stdout_buffer);
    const stdout = &stdout_file_writer.interface;

    var line_buf: [256]u8 = undefined;
    const line = hello.formatGreeting(&line_buf, name) catch {
        try stdout.print("Name is too long (max 240 bytes).\n", .{});
        try stdout.flush();
        return error.NameTooLong;
    };
    try stdout.writeAll(line);
    try stdout.flush();
}

fn isHelp(arg: []const u8) bool {
    return std.mem.eql(u8, arg, "-h") or std.mem.eql(u8, arg, "--help");
}

fn writeUsage(io: Io) !void {
    var stderr_buffer: [512]u8 = undefined;
    var stderr_file_writer: Io.File.Writer = .init(.stderr(), io, &stderr_buffer);
    const stderr = &stderr_file_writer.interface;
    try stderr.writeAll(
        \\Usage: hello [name]
        \\
        \\Prints a greeting. Defaults to "world" when no name is given.
        \\
    );
    try stderr.flush();
}
