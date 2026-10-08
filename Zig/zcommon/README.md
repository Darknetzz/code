# zcommon

Shared helpers for the Zig CLIs (Windows console UTF-8 and ANSI color).

## `setupTerminal`

Call once at the start of `main`:

```zig
const color = zcommon.setupTerminal(init.io, init.environ_map);
```

This:

1. Sets the console input/output code page to UTF-8 (`65001`) when stdin/stdout/stderr is a real console
2. Enables Windows VT / ANSI processing on TTY handles
3. Returns a `Color` handle (on by default for TTYs)

Color is off when `NO_COLOR` is set, forced on by `FORCE_COLOR` or `CLICOLOR_FORCE`, and skipped for redirected pipes unless forced.

## `Color`

```zig
try w.print("{s}Error:{s} boom\n", .{ color.s(.red), color.s(.reset) });
```

Styles: `reset`, `bold`, `dim`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`. Codes are empty strings when disabled, so the same format string works with or without color.

## Use as a dependency

In `build.zig.zon`:

```zig
.dependencies = .{
    .zcommon = .{ .path = "../zcommon" },
},
```
