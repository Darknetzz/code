"""Shared Playwright locator resolution for steps and form fields."""

from __future__ import annotations

import json
from typing import Literal

from playwright.async_api import Locator, Page

LocatorBy = Literal["role", "text", "css", "test_id", "label", "data"]


def normalize_data_attr(attr: str) -> str:
    """Normalize user input to a full data-* attribute name (e.g. cy -> data-cy)."""
    a = attr.strip()
    if not a:
        raise ValueError("data_attr is required")
    if a in ("testid", "test-id"):
        return "data-testid"
    if a.startswith("data-"):
        return a
    return f"data-{a}"


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
    data_attr: str | None = None,
    data_value: str | None = None,
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
    if by == "data":
        value = data_value or test_id
        if not value:
            raise ValueError("locator with by=data requires 'data_value'")
        attr = normalize_data_attr(data_attr or "data-testid")
        if attr == "data-testid":
            return page.get_by_test_id(value)
        return page.locator(f"[{attr}={json.dumps(value)}]")
    if by == "label":
        label_text = label or name or text
        if not label_text:
            raise ValueError("locator with by=label requires 'label', 'name', or 'text'")
        return page.get_by_label(label_text)
    raise ValueError(f"Unknown locator by: {by}")
