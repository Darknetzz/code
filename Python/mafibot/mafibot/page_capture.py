"""Capture ms.php shell plus iframe content for discovery/verification."""

from __future__ import annotations

from playwright.async_api import Page


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
