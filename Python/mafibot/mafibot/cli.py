"""Console entry point (delegates to root mafibot.py for now)."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "mafibot.py"
    sys.argv[0] = str(root)
    runpy.run_path(str(root), run_name="__main__")


if __name__ == "__main__":
    main()
