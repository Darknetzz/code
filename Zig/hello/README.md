# hello

Minimal Zig CLI that prints a greeting.

## Build

From this directory:

```powershell
zig build
```

The binary is written to `zig-out/bin/hello` (or `hello.exe` on Windows).

## Run

```powershell
zig build run
zig build run -- Zig
zig build run -- --help
```

Or after installing:

```powershell
.\zig-out\bin\hello.exe
.\zig-out\bin\hello.exe Alice
```

## Test

```powershell
zig build test
```
