"""Undersåtter (folk) page — parse roster and apply per-minion training."""

from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.async_api import Frame, Page

from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching
from mafibot.page_capture import capture_page_html
from mafibot.selectors import MINIONS_TRAIN_LABELS

MINION_TRAINING_TYPES: tuple[str, ...] = ("angrep", "beskyttelse", "intelligens")

_TRAINING_LABELS: dict[str, str] = {
    "angrep": "Angrep",
    "beskyttelse": "Beskyttelse",
    "intelligens": "Intelligens",
}

_FOLK_ROUTE = "game.php?p=folk&se=hoved"


@dataclass(frozen=True)
class MinionInfo:
    id: str | None
    name: str
    alive: bool
    training: str | None = None
    angrep: float | None = None
    beskyttelse: float | None = None
    intelligens: float | None = None


@dataclass(frozen=True)
class MinionsRoster:
    minions: tuple[MinionInfo, ...]

    @property
    def total(self) -> int:
        return len(self.minions)

    @property
    def alive_count(self) -> int:
        return sum(1 for m in self.minions if m.alive)

    @property
    def dead_count(self) -> int:
        return self.total - self.alive_count


def training_label(training_id: str) -> str:
    return _TRAINING_LABELS.get(training_id.lower(), training_id)


def _parse_skill_cells(row: str) -> tuple[float | None, float | None, float | None]:
    labels = ("Angrep", "Beskyttelse", "Intelligens")
    values: list[float | None] = []
    for label in labels:
        m = re.search(
            rf'app-table-extra">{label}:\s*</span>\s*<a[^>]*>([\d.]+)</a>',
            row,
            re.I,
        )
        if m:
            try:
                values.append(float(m.group(1)))
            except ValueError:
                values.append(None)
        else:
            values.append(None)
    return values[0], values[1], values[2]


def roster_skill_totals(roster: MinionsRoster) -> dict[str, float]:
    totals = {"angrep": 0.0, "beskyttelse": 0.0, "intelligens": 0.0}
    for m in roster.minions:
        if not m.alive:
            continue
        if m.angrep is not None:
            totals["angrep"] += m.angrep
        if m.beskyttelse is not None:
            totals["beskyttelse"] += m.beskyttelse
        if m.intelligens is not None:
            totals["intelligens"] += m.intelligens
    return {k: round(v, 1) for k, v in totals.items()}


def resolve_minion_training(profile: BotProfile, minion: MinionInfo) -> str | None:
    """Training type to apply for an alive minion, or None to skip."""
    if not minion.alive:
        return None
    want = (profile.minions_training or {}).get(minion.name)
    if not want:
        want = profile.minions_default_training or "angrep"
    want = str(want).lower().strip()
    if want not in MINION_TRAINING_TYPES:
        want = "angrep"
    return want


def parse_minions_from_html(html: str) -> MinionsRoster:
    """Parse Mine undersåtter table from folk page HTML (main or iframe chunk)."""
    start = html.find("Mine undersåtter")
    if start < 0:
        return MinionsRoster(())
    chunk = html[start:]
    end = chunk.find("</table>")
    if end >= 0:
        chunk = chunk[:end]
    minions: list[MinionInfo] = []
    for row in re.findall(
        r'<tr>\s*<td style="width: 40px;">.*?</tr>',
        chunk,
        flags=re.S | re.I,
    ):
        name_m = re.search(r"<td><a[^>]*>([^<]+)</a></td>", row, re.I)
        if not name_m:
            continue
        name = name_m.group(1).strip()
        alive = not re.search(r">\s*DØD\s*<", row, re.I)
        mid: str | None = None
        training: str | None = None
        sel_m = re.search(r"treningstype_(\d+)", row, re.I)
        if sel_m:
            mid = sel_m.group(1)
            opt_m = re.search(
                r'<select[^>]*>.*?<option value="([^"]+)"[^>]*\sselected',
                row,
                re.S | re.I,
            )
            if not opt_m:
                opt_m = re.search(
                    r'<select[^>]*>\s*<option value="([^"]+)"',
                    row,
                    re.S | re.I,
                )
            if opt_m:
                training = opt_m.group(1).lower().strip()
        elif not alive:
            hide_m = re.search(r"folk_skjul\(\{id:\s*(\d+)", row, re.I)
            if hide_m:
                mid = hide_m.group(1)
        angrep, beskyttelse, intelligens = _parse_skill_cells(row)
        minions.append(
            MinionInfo(
                id=mid,
                name=name,
                alive=alive,
                training=training,
                angrep=angrep,
                beskyttelse=beskyttelse,
                intelligens=intelligens,
            )
        )
    return MinionsRoster(tuple(minions))


async def content_frame(page: Page) -> Frame | Page:
    frame = page.frame(name="hovedinnhold")
    return frame if frame is not None else page


async def ensure_folk_train_page(
    page: Page,
    *,
    policy: HumanPolicy | None = None,
    dry_run: bool = False,
) -> Frame | Page:
    from mafibot.navigation import goto_page

    await goto_page(page, "minions", policy=policy, dry_run=dry_run)
    target = await content_frame(page)
    if dry_run:
        return target
    await target.goto(
        f"https://mafiaspillet.no/{_FOLK_ROUTE}",
        wait_until="domcontentloaded",
    )
    await page_reading_pause(page)
    return target


async def parse_minions_page(page: Page) -> MinionsRoster:
    html = await capture_page_html(page)
    return parse_minions_from_html(html)


async def apply_minions_training(
    page: Page,
    profile: BotProfile,
    roster: MinionsRoster,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Set treningstype selects to match profile; returns names updated."""
    target = await content_frame(page)
    updated: list[str] = []
    for minion in roster.minions:
        want = resolve_minion_training(profile, minion)
        if not want or not minion.id:
            continue
        if minion.training and minion.training.lower() == want:
            continue
        sel = target.locator(f"#treningstype_{minion.id}")
        if await sel.count() == 0:
            continue
        if dry_run:
            updated.append(minion.name)
            continue
        box = sel.first
        if not await box.is_visible():
            continue
        try:
            await box.select_option(value=want)
        except Exception:
            await box.select_option(label=training_label(want))
        updated.append(minion.name)
    return updated


async def click_train_all(
    page: Page,
    *,
    policy: HumanPolicy | None = None,
    dry_run: bool = False,
) -> bool:
    labels = MINIONS_TRAIN_LABELS + ("tren alle", "tren alle!")
    return bool(
        await click_button_matching(page, labels, policy=policy, dry_run=dry_run)
    )
