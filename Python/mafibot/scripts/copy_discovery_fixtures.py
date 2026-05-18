"""Copy discovery HTML into tests/fixtures/discovered (redact tokens)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from mafibot.verify_pages import ACTION_PAGES

DEFAULT_SRC = Path.home() / "AppData/Roaming/mafibot/discovery"


def main() -> None:
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
        if not src.is_dir():
            raise SystemExit(f"Not a directory: {src}")
    else:
        src_root = DEFAULT_SRC
        runs = sorted((p for p in src_root.iterdir() if p.is_dir()), key=lambda p: p.name)
        if not runs:
            raise SystemExit(f"No discovery runs under {src_root}")
        src = runs[-1]
    dst = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "discovered"
    dst.mkdir(parents=True, exist_ok=True)
    for logical in ACTION_PAGES:
        path = src / f"{logical}.html"
        if not path.is_file():
            raise SystemExit(f"Missing {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r'value="[a-f0-9]{32}"', 'value="REDACTED"', text)
        out = dst / f"{logical}.html"
        out.write_text(text, encoding="utf-8")
        print(f"{logical}: {len(text)} bytes <- {src.name}")


if __name__ == "__main__":
    main()
