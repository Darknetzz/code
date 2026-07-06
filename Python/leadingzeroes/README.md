# leadingzeroes

> **Legacy / reference implementation.** For CPU brute-force hash search with leading or trailing zero runs, use [`Rust/rust-hash-zero`](../../Rust/rust-hash-zero/) (`rust-hash-zero` CLI). Keep this Python version only if you need **OpenCL GPU** acceleration, **recurring-pattern** search modes, or the Rich progress UI.

CLI for finding SHA-256 hashes with leading zero runs, optional OpenCL GPU acceleration, and recurring-pattern modes.

## Requirements

```powershell
pip install -r requirements.txt
```

Optional GPU support:

```powershell
pip install pyopencl numpy
```

## Quick start

```powershell
python leadingzeroes.py --help
python leadingzeroes-simple.py
```

See [`Rust/rust-hash-zero/README.md`](../../Rust/rust-hash-zero/README.md) for the recommended `find` / `verify` workflow.
