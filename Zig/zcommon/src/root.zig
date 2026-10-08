const std = @import("std");
const builtin = @import("builtin");
const Io = std.Io;

/// UTF-8 console code page (Windows) plus ANSI color setup.
/// Returns a `Color` handle for optional styling.
pub fn setupTerminal(io: Io, environ: *const std.process.Environ.Map) Color {
    enableUtf8();
    return Color.init(io, environ);
}

/// If stdin/stdout/stderr is a real console, switch that console to UTF-8
/// (`CP_UTF8` / 65001) so `WriteFile` of UTF-8 bytes renders correctly.
/// No-op when those handles are redirected, or on non-Windows.
pub fn enableUtf8() void {
    if (comptime builtin.os.tag != .windows) return;
    windowsEnableUtf8();
}

const k32 = struct {
    extern "kernel32" fn GetConsoleMode(hConsoleHandle: std.os.windows.HANDLE, lpMode: *std.os.windows.DWORD) callconv(.winapi) std.os.windows.BOOL;
    extern "kernel32" fn SetConsoleOutputCP(wCodePageID: std.os.windows.UINT) callconv(.winapi) std.os.windows.BOOL;
    extern "kernel32" fn SetConsoleCP(wCodePageID: std.os.windows.UINT) callconv(.winapi) std.os.windows.BOOL;
};

fn windowsEnableUtf8() void {
    const CP_UTF8: std.os.windows.UINT = 65001;
    const params = std.os.windows.peb().ProcessParameters;
    if (isConsole(params.hStdOutput) or isConsole(params.hStdError)) {
        _ = k32.SetConsoleOutputCP(CP_UTF8);
    }
    if (isConsole(params.hStdInput)) {
        _ = k32.SetConsoleCP(CP_UTF8);
    }
}

fn isConsole(handle: std.os.windows.HANDLE) bool {
    var mode: std.os.windows.DWORD = undefined;
    return k32.GetConsoleMode(handle, &mode) != .FALSE;
}

pub const Style = enum {
    reset,
    bold,
    dim,
    red,
    green,
    yellow,
    blue,
    magenta,
    cyan,
};

/// Lightweight ANSI styling. Codes are empty strings when disabled.
pub const Color = struct {
    enabled: bool,

    /// On by default when stdout or stderr is a TTY.
    /// Off when `NO_COLOR` is set. Forced on by `FORCE_COLOR` or `CLICOLOR_FORCE`
    /// (even when redirected). Enables Windows VT processing when possible.
    pub fn init(io: Io, environ: *const std.process.Environ.Map) Color {
        const force = envTruthy(environ, "FORCE_COLOR") or envTruthy(environ, "CLICOLOR_FORCE");
        const no_color = environ.get("NO_COLOR") != null;

        const stdout = Io.File.stdout();
        const stderr = Io.File.stderr();
        const out_tty = stdout.isTty(io) catch false;
        const err_tty = stderr.isTty(io) catch false;

        if (out_tty) stdout.enableAnsiEscapeCodes(io) catch {};
        if (err_tty) stderr.enableAnsiEscapeCodes(io) catch {};

        const enabled = if (no_color)
            false
        else if (force)
            true
        else
            out_tty or err_tty;

        return .{ .enabled = enabled };
    }

    pub fn off() Color {
        return .{ .enabled = false };
    }

    /// ANSI escape for `style`, or "" when color is disabled.
    pub fn s(self: Color, style: Style) []const u8 {
        if (!self.enabled) return "";
        return switch (style) {
            .reset => "\x1b[0m",
            .bold => "\x1b[1m",
            .dim => "\x1b[2m",
            .red => "\x1b[31m",
            .green => "\x1b[32m",
            .yellow => "\x1b[33m",
            .blue => "\x1b[34m",
            .magenta => "\x1b[35m",
            .cyan => "\x1b[36m",
        };
    }
};

fn envTruthy(environ: *const std.process.Environ.Map, key: []const u8) bool {
    const v = environ.get(key) orelse return false;
    if (v.len == 0) return false;
    if (std.mem.eql(u8, v, "0")) return false;
    return true;
}

test "enableUtf8 is safe to call" {
    enableUtf8();
}

test "Color.off yields empty codes" {
    const c = Color.off();
    try std.testing.expect(!c.enabled);
    try std.testing.expectEqualStrings("", c.s(.red));
    try std.testing.expectEqualStrings("", c.s(.reset));
}

test "Color.enabled yields ANSI codes" {
    const c: Color = .{ .enabled = true };
    try std.testing.expectEqualStrings("\x1b[31m", c.s(.red));
    try std.testing.expectEqualStrings("\x1b[0m", c.s(.reset));
}
