"""Shared Playwright locator resolution for steps and form fields."""

from __future__ import annotations

from typing import Literal

from playwright.async_api import Locator, Page

LocatorBy = Literal["role", "text", "css", "test_id", "label"]


def resolve_locator(
    page: Page,
    *,
    by: LocatorBy | str,
    role: str | None = None,
    name: str | None = None,
    text: str | None = None,
    selector: str | None = None,
    test_id: str | None = None,
    label: str | None = None,
) -> Locator:
    if by == "role":
        if not role:
            raise ValueError("locator with by=role requires 'role'")
        return page.get_by_role(role, name=name or None)
    if by == "text":
        if not text:
            raise ValueError("locator with by=text requires 'text'")
        return page.get_by_text(text)
    if by == "css":
        if not selector:
            raise ValueError("locator with by=css requires 'selector'")
        return page.locator(selector)
    if by == "test_id":
        if not test_id:
            raise ValueError("locator with by=test_id requires 'test_id'")
        return page.get_by_test_id(test_id)
    if by == "label":
        label_text = label or name or text
        if not label_text:
            raise ValueError("locator with by=label requires 'label', 'name', or 'text'")
        return page.get_by_label(label_text)
    raise ValueError(f"Unknown locator by: {by}")
