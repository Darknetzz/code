const std = @import("std");
const Io = std.Io;
const hello = @import("hello");
const zcommon = @import("zcommon");

pub fn main(init: std.process.Init) !void {
    const color = zcommon.setupTerminal(init.io, init.environ_map);
    const arena = init.arena.allocator();
    const args = try init.minimal.args.toSlice(arena);

    if (args.len >= 2 and isHelp(args[1])) {
        try writeUsage(init.io, color);
        return;
    }

    const name = if (args.len >= 2) args[1] else hello.default_name;

    var stdout_buffer: [1024]u8 = undefined;
    var stdout_file_writer: Io.File.Writer = .init(.stdout(), init.io, &stdout_buffer);
    const stdout = &stdout_file_writer.interface;

    if (name.len > 240) {
        try stdout.print("{s}Name is too long (max 240 bytes).{s}\n", .{ color.s(.red), color.s(.reset) });
        try stdout.flush();
        return error.NameTooLong;
    }
    try stdout.print("Hello, {s}{s}{s}!\n", .{ color.s(.cyan), name, color.s(.reset) });
    try stdout.flush();
}

fn isHelp(arg: []const u8) bool {
    return std.mem.eql(u8, arg, "-h") or std.mem.eql(u8, arg, "--help");
}

fn writeUsage(io: Io, color: zcommon.Color) !void {
    var stderr_buffer: [512]u8 = undefined;
    var stderr_file_writer: Io.File.Writer = .init(.stderr(), io, &stderr_buffer);
    const stderr = &stderr_file_writer.interface;
    try stderr.print("{s}Usage:{s} hello [name]\n\n", .{ color.s(.bold), color.s(.reset) });
    try stderr.writeAll("Prints a greeting. Defaults to \"world\" when no name is given.\n");
    try stderr.flush();
}
