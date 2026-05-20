"""Reorder config panel: Profile → Actions → Session → Hotel → Pacing → Notifications."""

from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "mafibot/static/index.html"


def slice_details(html: str, summary: str) -> tuple[str, str]:
    pattern = rf"<details class=\"config-section\"[^>]*>\s*<summary>{re.escape(summary)}</summary>"
    m = re.search(pattern, html)
    if not m:
        raise ValueError(f"Section not found: {summary}")
    start = m.start()
    depth = 0
    i = m.start()
    while i < len(html):
        if html.startswith("<details", i):
            depth += 1
            i += 7
            continue
        if html.startswith("</details>", i):
            depth -= 1
            i += len("</details>")
            if depth == 0:
                block = html[start:i]
                return html[:start] + html[i:], block
            continue
        i += 1
    raise ValueError(f"Unclosed section: {summary}")


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")

    sections = [
        "Session",
        "Hotel &amp; safety",
        "Human pacing",
        "Actions",
    ]
    blocks: dict[str, str] = {}
    for summary in sections:
        html, blocks[summary] = slice_details(html, summary)

    insert_point = re.search(
        r"<details class=\"config-section\">\s*<summary>Notifications</summary>",
        html,
    )
    if not insert_point:
        raise ValueError("Notifications section not found")

    global_blocks = (
        f"\n        {blocks['Session'].strip()}\n"
        f"        {blocks['Hotel &amp; safety'].strip()}\n"
        f"        {blocks['Human pacing'].strip()}\n"
    )

    actions = blocks["Actions"]
    actions = actions.replace(
        "Actions (priority top → bottom)",
        "Priority (top runs first)",
    )
    actions = re.sub(
        r"<h3 class=\"action-options-heading\">Action options</h3>",
        '<h3 class="action-options-heading">Per-action settings</h3>',
        actions,
        count=1,
    )
    # Close action-options div before Actions </details>
    if "</motion.div>" not in actions and 'id="action-options-section"' in actions:
        actions = re.sub(
            r"(</details>\s*\n)(\s*</details>\s*\n)(?=\s*<details class=\"config-section\">\s*\n\s*<summary>Notifications)",
            r"\1        </div>\n\2",
            actions,
            count=1,
        )
    elif re.search(
        r"</details>\s*\n\s*</details>\s*\n\s*<details class=\"config-section\">\s*\n\s*<summary>Notifications",
        actions,
    ):
        actions = re.sub(
            r"</details>\s*\n\s*</details>",
            "</details>\n        </motion.div>\n        </details>",
            actions,
            count=1,
        )
        actions = actions.replace("</motion.div>", "</div>", 1)

    # Insert Actions right after Profile section
    profile_end = re.search(
        r"(<details class=\"config-section\" open>\s*<summary>Profile</summary>.*?</details>)",
        html,
        re.S,
    )
    if not profile_end:
        raise ValueError("Profile section not found")
    html = (
        html[: profile_end.end()]
        + "\n        "
        + actions.strip()
        + "\n"
        + global_blocks
        + html[insert_point.start() :]
    )

    INDEX.write_text(html, encoding="utf-8")
    print("OK:", INDEX)


if __name__ == "__main__":
    main()
