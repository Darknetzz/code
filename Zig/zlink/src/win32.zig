const std = @import("std");
const windows = std.os.windows;

pub const FILE_ATTRIBUTE_REPARSE_POINT: windows.DWORD = 0x400;
pub const FILE_ATTRIBUTE_DIRECTORY: windows.DWORD = 0x10;
pub const INVALID_FILE_ATTRIBUTES: windows.DWORD = 0xFFFFFFFF;
pub const DRIVE_REMOTE: windows.UINT = 4;
pub const ERROR_PRIVILEGE_NOT_HELD: u32 = 1314;

extern "kernel32" fn GetFileAttributesW(lpFileName: windows.LPCWSTR) callconv(.winapi) windows.DWORD;
extern "kernel32" fn GetDriveTypeW(lpRootPathName: ?windows.LPCWSTR) callconv(.winapi) windows.UINT;
extern "kernel32" fn CreateDirectoryW(lpPathName: windows.LPCWSTR, lpSecurityAttributes: ?*anyopaque) callconv(.winapi) windows.BOOL;
extern "kernel32" fn RemoveDirectoryW(lpPathName: windows.LPCWSTR) callconv(.winapi) windows.BOOL;
extern "kernel32" fn CreateHardLinkW(
    lpFileName: windows.LPCWSTR,
    lpExistingFileName: windows.LPCWSTR,
    lpSecurityAttributes: ?*anyopaque,
) callconv(.winapi) windows.BOOL;
extern "kernel32" fn CreateFileW(
    lpFileName: windows.LPCWSTR,
    dwDesiredAccess: windows.DWORD,
    dwShareMode: windows.DWORD,
    lpSecurityAttributes: ?*anyopaque,
    dwCreationDisposition: windows.DWORD,
    dwFlagsAndAttributes: windows.DWORD,
    hTemplateFile: ?windows.HANDLE,
) callconv(.winapi) windows.HANDLE;
extern "kernel32" fn DeviceIoControl(
    hDevice: windows.HANDLE,
    dwIoControlCode: windows.DWORD,
    lpInBuffer: ?*const anyopaque,
    nInBufferSize: windows.DWORD,
    lpOutBuffer: ?*anyopaque,
    nOutBufferSize: windows.DWORD,
    lpBytesReturned: ?*windows.DWORD,
    lpOverlapped: ?*anyopaque,
) callconv(.winapi) windows.BOOL;

const GENERIC_WRITE: windows.DWORD = 0x40000000;
const FILE_SHARE_READ: windows.DWORD = 0x1;
const FILE_SHARE_WRITE: windows.DWORD = 0x2;
const FILE_SHARE_DELETE: windows.DWORD = 0x4;
const OPEN_EXISTING: windows.DWORD = 3;
const FILE_FLAG_BACKUP_SEMANTICS: windows.DWORD = 0x02000000;
const FILE_FLAG_OPEN_REPARSE_POINT: windows.DWORD = 0x00200000;
const FSCTL_SET_REPARSE_POINT: windows.DWORD = 0x000900A4;
const IO_REPARSE_TAG_MOUNT_POINT: u32 = 0xA0000003;

pub const Attrs = struct {
    raw: windows.DWORD,

    pub fn missing(self: Attrs) bool {
        return self.raw == INVALID_FILE_ATTRIBUTES;
    }

    pub fn reparse(self: Attrs) bool {
        return !self.missing() and self.raw & FILE_ATTRIBUTE_REPARSE_POINT != 0;
    }

    pub fn directory(self: Attrs) bool {
        return !self.missing() and self.raw & FILE_ATTRIBUTE_DIRECTORY != 0;
    }
};

pub fn attributes(allocator: std.mem.Allocator, file_path: []const u8) !Attrs {
    const w = try std.unicode.wtf8ToWtf16LeAllocZ(allocator, file_path);
    defer allocator.free(w);
    return .{ .raw = GetFileAttributesW(w.ptr) };
}

pub fn getDriveType(allocator: std.mem.Allocator, root: []const u8) u32 {
    var buf = [_]u8{ 'X', ':', '\\' };
    if (root.len >= 2 and root[1] == ':') {
        buf[0] = std.ascii.toUpper(root[0]);
        const w = std.unicode.wtf8ToWtf16LeAllocZ(allocator, buf[0..3]) catch return 1;
        defer allocator.free(w);
        return GetDriveTypeW(w.ptr);
    }
    return 1;
}

fn driveTypeForPath(allocator: std.mem.Allocator, file_path: []const u8) u32 {
    const zlink = @import("zlink");
    const root = zlink.driveRoot(file_path) orelse return 1;
    return getDriveType(allocator, root);
}

pub fn isRemotePath(allocator: std.mem.Allocator, file_path: []const u8) bool {
    const zlink = @import("zlink");
    if (zlink.isUncPath(file_path)) return true;
    return driveTypeForPath(allocator, file_path) == DRIVE_REMOTE;
}

fn toNtPath(allocator: std.mem.Allocator, abs: []const u8) ![]u8 {
    const zlink = @import("zlink");
    if (std.ascii.startsWithIgnoreCase(abs, "\\\\?\\UNC\\")) {
        return std.fmt.allocPrint(allocator, "\\??\\UNC\\{s}", .{abs["\\\\?\\UNC\\".len..]});
    }
    if (std.mem.startsWith(u8, abs, "\\\\?\\") or std.mem.startsWith(u8, abs, "\\??\\")) {
        return std.fmt.allocPrint(allocator, "\\??\\{s}", .{abs[4..]});
    }
    if (zlink.isUncPath(abs)) {
        const rest = if (abs.len >= 2) abs[2..] else abs;
        return std.fmt.allocPrint(allocator, "\\??\\UNC\\{s}", .{rest});
    }
    return std.fmt.allocPrint(allocator, "\\??\\{s}", .{abs});
}

pub fn createHardLink(allocator: std.mem.Allocator, link_path: []const u8, target_abs: []const u8) !void {
    const link_w = try std.unicode.wtf8ToWtf16LeAllocZ(allocator, link_path);
    defer allocator.free(link_w);
    const target_w = try std.unicode.wtf8ToWtf16LeAllocZ(allocator, target_abs);
    defer allocator.free(target_w);
    if (CreateHardLinkW(link_w.ptr, target_w.ptr, null) == .FALSE) return error.CreateHardLinkFailed;
}

pub fn createJunction(allocator: std.mem.Allocator, link_path: []const u8, target_abs: []const u8) !void {
    const nt_target = try toNtPath(allocator, target_abs);
    defer allocator.free(nt_target);

    const link_w = try std.unicode.wtf8ToWtf16LeAllocZ(allocator, link_path);
    defer allocator.free(link_w);
    const subst_w = try std.unicode.wtf8ToWtf16LeAllocZ(allocator, nt_target);
    defer allocator.free(subst_w);
    const print_w = try std.unicode.wtf8ToWtf16LeAllocZ(allocator, target_abs);
    defer allocator.free(print_w);

    if (CreateDirectoryW(link_w.ptr, null) == .FALSE) return error.CreateJunctionFailed;
    var keep_dir = true;
    errdefer if (keep_dir) {
        _ = RemoveDirectoryW(link_w.ptr);
    };

    const handle = CreateFileW(
        link_w.ptr,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        null,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        null,
    );
    if (handle == windows.INVALID_HANDLE_VALUE) return error.CreateJunctionFailed;
    defer windows.CloseHandle(handle);

    const subst_bytes: usize = subst_w.len * 2;
    const print_bytes: usize = print_w.len * 2;
    const pathbuf_bytes = subst_bytes + 2 + print_bytes + 2;
    const reparse_data_length: u16 = @intCast(8 + pathbuf_bytes);
    const total: usize = 8 + reparse_data_length;

    const buf = try allocator.alloc(u8, total);
    defer allocator.free(buf);
    @memset(buf, 0);

    std.mem.writeInt(u32, buf[0..4], IO_REPARSE_TAG_MOUNT_POINT, .little);
    std.mem.writeInt(u16, buf[4..6], reparse_data_length, .little);
    std.mem.writeInt(u16, buf[6..8], 0, .little);
    std.mem.writeInt(u16, buf[8..10], 0, .little);
    std.mem.writeInt(u16, buf[10..12], @intCast(subst_bytes), .little);
    std.mem.writeInt(u16, buf[12..14], @intCast(subst_bytes + 2), .little);
    std.mem.writeInt(u16, buf[14..16], @intCast(print_bytes), .little);
    @memcpy(buf[16..][0..subst_bytes], std.mem.sliceAsBytes(subst_w[0..subst_w.len]));
    @memcpy(buf[16 + subst_bytes + 2 ..][0..print_bytes], std.mem.sliceAsBytes(print_w[0..print_w.len]));

    var bytes_returned: windows.DWORD = 0;
    if (DeviceIoControl(
        handle,
        FSCTL_SET_REPARSE_POINT,
        buf.ptr,
        @intCast(buf.len),
        null,
        0,
        &bytes_returned,
        null,
    ) == .FALSE) return error.CreateJunctionFailed;

    keep_dir = false;
}

pub fn lastError() u32 {
    return @intFromEnum(windows.GetLastError());
}
