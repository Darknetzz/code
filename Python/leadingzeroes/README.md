# leadingzeroes

> **Legacy / reference implementation.** For CPU brute-force hash search with leading or trailing zero runs, use the canonical Rust tool [`Rust/hash-zero`](../../Rust/hash-zero/). Keep this Python version only if you need **OpenCL GPU** acceleration, **recurring-pattern** search modes, or the Rich progress UI.

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

See [`Rust/hash-zero/README.md`](../../Rust/hash-zero/README.md) for the recommended `find` / `verify` workflow.
