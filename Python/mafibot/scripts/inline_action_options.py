"""Convert action option panels to divs in a hidden host (for per-row mount)."""

from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "mafibot/static/index.html"


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")
    start = html.index('<div id="action-options-section"')
    end = html.index(
        '        </details>\n\n        <details class="config-section">\n          <summary>Session</summary>',
        start,
    )
    block = html[start:end]
    block = re.sub(
        r'<motion.div id="action-options-section"[^>]*>\s*<h3[^>]*>.*?</h3>\s*',
        "",
        block,
        count=1,
        flags=re.S,
    )
    block = re.sub(
        r'<div id="action-options-section"[^>]*>\s*<h3[^>]*>.*?</h3>\s*',
        '<div id="action-options-host" class="action-options-host" hidden aria-hidden="true">\n',
        block,
        count=1,
        flags=re.S,
    )
    block = re.sub(
        r'<details id="(action-options-[^"]+)" class="action-options-panel hidden">\s*<summary>[^<]*</summary>\s*',
        r'<div id="\1" class="action-item-options-panel">',
        block,
    )
    block = block.replace("</details>", "</div>")
    html = html[:start] + block + html[end:]
    INDEX.write_text(html, encoding="utf-8")
    print("OK", INDEX)


if __name__ == "__main__":
    main()
