const std = @import("std");
const builtin = @import("builtin");

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

test "enableUtf8 is safe to call" {
    enableUtf8();
}
