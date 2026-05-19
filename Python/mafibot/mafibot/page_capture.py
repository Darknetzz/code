"""Capture ms.php shell plus iframe content for discovery/verification."""

from __future__ import annotations

import re

from playwright.async_api import Page


async def collect_page_text(page: Page) -> str:
    """Main frame text plus each child frame (game content lives in iframes)."""
    chunks: list[str] = []
    try:
        chunks.append(await page.locator("body").inner_text())
    except Exception:
        pass
    for frame in getattr(page, "frames", []):
        if frame == getattr(page, "main_frame", None):
            continue
        try:
            chunks.append(await frame.locator("body").inner_text())
        except Exception:
            continue
    return "\n".join(chunks)


async def capture_page_html(page: Page) -> str:
    """Main frame HTML plus each child frame (game content lives in iframes)."""
    chunks: list[str] = [await page.content()]
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            body = await frame.locator("body").inner_html()
        except Exception:
            continue
        name = frame.name or frame.url or "anonymous"
        chunks.append(f"<!-- iframe:{name} -->\n{body}")
    return "\n".join(chunks)


def html_to_plain_text(html: str) -> str:
    """Strip HTML to plain text, including iframe comment blocks from discovery snapshots."""
    chunks: list[str] = []
    for part in re.split(r"<!--\s*iframe:[^>]+-->", html, flags=re.I):
        body = re.search(r"<body[^>]*>(.*)</body>", part, re.I | re.S)
        raw = body.group(1) if body else part
        raw = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
        raw = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
        raw = re.sub(r"<[^>]+>", "\n", raw)
        chunks.append(re.sub(r"\n+", "\n", raw).strip())
    return "\n".join(c for c in chunks if c)
