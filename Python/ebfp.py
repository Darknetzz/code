"""
Tiny eBPF demo using BCC.

This script attaches a kprobe to the kernel's execve() syscall and prints a
message every time a process is started.

It is intentionally simple, but heavily commented and has a few safety checks
to make it friendlier to run on different systems.
"""

import sys
import os
import platform

try:
    # bcc is an external dependency, not part of the standard library.
    # ImportError will be handled below with a clear error message.
    from bcc import BPF
except ImportError as exc:  # pragma: no cover - environment‑specific
    sys.stderr.write(
        "ERROR: The 'bcc' Python package is not installed.\n"
        "Install it with (on most systems):\n"
        "  pip install bcc\n"
        "and make sure the BCC / eBPF tools are installed from your distro.\n"
    )
    sys.exit(1)


def ensure_supported_environment() -> None:
    """
    Perform some basic environment checks before attempting to load eBPF:

    - Require Linux (eBPF with BCC is a Linux kernel feature).
    - Require root privileges (or effective UID 0) to attach kprobes.
    """
    # 1) OS check: BCC + eBPF only makes sense on Linux.
    system = platform.system()
    if system != "Linux":
        sys.stderr.write(
            f"ERROR: This script only runs on Linux (current system: {system}).\n"
        )
        sys.exit(1)

    # 2) Privilege check: attaching kprobes requires root.
    # On some exotic environments os.geteuid might not exist; handle that.
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None:
        sys.stderr.write(
            "ERROR: Cannot determine effective UID on this platform.\n"
            "This script is intended to be run as root on Linux.\n"
        )
        sys.exit(1)

    if geteuid() != 0:
        sys.stderr.write(
            "ERROR: This script must be run as root to attach eBPF kprobes.\n"
            "Try again with: sudo python3 ebfp.py\n"
        )
        sys.exit(1)


def main() -> None:
    """
    Set up a minimal eBPF program via BCC and start tracing execve().

    High‑level steps:
    1. Validate that we are on a supported system (Linux + root).
    2. Define a small eBPF program (in C) that will run in kernel space.
    3. Load that program into the kernel using BCC.
    4. Attach it to the execve() syscall via a kprobe.
    5. Stream the trace output back to user space.
    """

    # Ensure we are on Linux, running as root, etc.
    ensure_supported_environment()

    # The eBPF program itself, written in a restricted C dialect.
    #
    # - int hello(void *ctx) is the function that will be called by the kernel
    #   when the attached event (kprobe) fires.
    # - bpf_trace_printk() writes a message into the kernel's trace pipe.
    #   BCC's b.trace_print() below will read from that pipe and display it.
    program = """
    int hello(void *ctx) {
        bpf_trace_printk("Surprise! A process was started.\\n");
        return 0;
    }
    """

    # Load the eBPF program into the kernel.
    # If this fails, BCC will typically raise a BCCException with details
    # (e.g. kernel too old, missing eBPF features, invalid program, etc.).
    try:
        b = BPF(text=program)
    except Exception as exc:  # pragma: no cover - kernel / env specific
        sys.stderr.write(
            "ERROR: Failed to load eBPF program via BCC.\n"
            f"Details: {exc}\n"
        )
        sys.exit(1)

    # Attach the eBPF program to the execve() syscall via a kprobe.
    # get_syscall_fnname("execve") resolves the appropriate kernel symbol
    # name for the current architecture / kernel version.
    try:
        b.attach_kprobe(event=b.get_syscall_fnname("execve"), fn_name="hello")
    except Exception as exc:  # pragma: no cover - kernel / env specific
        sys.stderr.write(
            "ERROR: Failed to attach kprobe to execve().\n"
            "Make sure your kernel supports kprobes/eBPF and that BCC is "
            "correctly installed.\n"
            f"Details: {exc}\n"
        )
        sys.exit(1)

    print("Tracing execve()... Press Ctrl+C to stop.")

    # This will block and continuously print messages from the kernel trace pipe.
    # Ctrl+C (SIGINT) will normally stop the script and detach the probes.
    try:
        b.trace_print()
    except KeyboardInterrupt:
        print("\nStopping trace and detaching kprobes...")
    except Exception as exc:  # pragma: no cover - runtime / env specific
        sys.stderr.write(f"\nERROR: Trace failed: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()