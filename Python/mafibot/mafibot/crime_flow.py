"""Configure and submit crime / steal on the Kriminalitet tab."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, click_option_matching
from mafibot.page_actions import fill_murder_target
from mafibot.profile_options import (
    crime_entry_labels,
    crime_perform_variant_labels,
    crime_steal_item_labels,
    crime_steal_target_mode,
    crime_steal_username,
    crime_submit_labels,
)

STEAL_RANDOM_TARGET_LABELS = (
    "tilfeldig",
    "random",
    "trekk",
    "velg tilfeldig",
    "tilfeldig spiller",
    "tilfeldig bruker",
)


async def run_crime_flow(
    page: Page,
    profile: BotProfile,
    *,
    policy: HumanPolicy,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Run perform or steal flow on the crime tab.
    Returns (success, detail message).
    """
    if profile.crime_kind == "steal":
        return await _run_steal_flow(page, profile, policy=policy, dry_run=dry_run)
    return await _run_perform_flow(page, profile, policy=policy, dry_run=dry_run)


async def _run_perform_flow(
    page: Page,
    profile: BotProfile,
    *,
    policy: HumanPolicy,
    dry_run: bool,
) -> tuple[bool, str]:
    variants = crime_perform_variant_labels(profile)
    if variants:
        if not await click_option_matching(page, variants, policy=policy, dry_run=dry_run):
            return False, f"perform: variant not found ({', '.join(variants)})"
        await page_reading_pause(page)

    entry = crime_entry_labels(profile)
    if not await click_button_matching(page, entry, policy=policy, dry_run=dry_run):
        return False, "perform: Utfør button not found or disabled"
    return True, "perform crime submitted"


async def _run_steal_flow(
    page: Page,
    profile: BotProfile,
    *,
    policy: HumanPolicy,
    dry_run: bool,
) -> tuple[bool, str]:
    entry = crime_entry_labels(profile)
    if not await click_button_matching(page, entry, policy=policy, dry_run=dry_run):
        return False, "steal: Stjel entry not found or disabled"
    await page_reading_pause(page)

    items = crime_steal_item_labels(profile)
    if items:
        if not await click_option_matching(page, items, policy=policy, dry_run=dry_run):
            return False, f"steal: item not found ({', '.join(items)})"
        await page_reading_pause(page)

    mode = crime_steal_target_mode(profile)
    if mode == "specific":
        username = crime_steal_username(profile)
        if not username:
            return False, "steal: specific target mode but no username configured"
        if not await fill_murder_target(page, username, policy=policy, dry_run=dry_run):
            return False, f"steal: could not fill target username ({username})"
        await page_reading_pause(page)
    else:
        if not await click_button_matching(
            page,
            STEAL_RANDOM_TARGET_LABELS,
            policy=policy,
            dry_run=dry_run,
        ):
            # Random target may be implicit on the steal form — continue to submit.
            pass
        else:
            await page_reading_pause(page)

    submit = crime_submit_labels(profile)
    if await click_button_matching(page, submit, policy=policy, dry_run=dry_run):
        detail = f"steal submitted ({items[0] if items else 'default'}, {mode})"
        return True, detail
    if mode == "specific" and await click_button_matching(
        page, entry, policy=policy, dry_run=dry_run
    ):
        return True, f"steal submitted via entry ({items[0] if items else 'default'})"
    return False, "steal: confirm/submit button not found"
