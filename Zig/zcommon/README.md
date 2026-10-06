# zcommon

Shared helpers for the Zig CLIs (Windows console UTF-8).

`enableUtf8()` sets the console input/output code page to UTF-8 (`65001`) when stdin, stdout, or stderr is a real console. Zig still writes UTF-8 bytes with `WriteFile`; this tells conhost/Windows Terminal to decode them as UTF-8 instead of the OEM page (often CP437). Redirected pipes and files are left unchanged.

## Use

In `build.zig.zon`:

```zig
.dependencies = .{
    .zcommon = .{ .path = "../zcommon" },
},
```

Call `zcommon.enableUtf8()` at the start of `main`.
