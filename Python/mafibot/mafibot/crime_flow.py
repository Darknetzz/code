"""Configure and submit crime on the Kriminalitet tab (enkel / tung / stjel)."""

from __future__ import annotations

from playwright.async_api import Page

from mafibot.config import BotProfile
from mafibot.crime_catalog import (
    crime_actions_enabled,
    option_match_labels,
    pick_crime_section,
    pick_option_ids,
    section_submit_labels,
)
from mafibot.human_policy import HumanPolicy, maybe_think_pause, page_reading_pause
from mafibot.navigation import click_button_matching, click_option_matching
from mafibot.page_actions import fill_murder_target
from mafibot.profile_options import (
    crime_steal_target_mode,
    crime_steal_username,
    crime_submit_labels,
)
from mafibot.selectors import STEAL_RANDOM_TARGET_LABELS


async def run_crime_flow(
    page: Page,
    profile: BotProfile,
    *,
    policy: HumanPolicy,
    dry_run: bool = False,
) -> tuple[bool, str]:
    section = pick_crime_section(profile)
    if section == "stjel":
        return await _run_stjel_flow(page, profile, policy=policy, dry_run=dry_run)
    return await _run_perform_section_flow(
        page, profile, section, policy=policy, dry_run=dry_run
    )


async def _run_perform_section_flow(
    page: Page,
    profile: BotProfile,
    section_id: str,
    *,
    policy: HumanPolicy,
    dry_run: bool,
) -> tuple[bool, str]:
    option_ids = pick_option_ids(profile, section_id)
    picked_label: str | None = None
    for opt_id in option_ids:
        labels = option_match_labels(section_id, opt_id)
        if await click_option_matching(page, labels, policy=policy, dry_run=dry_run):
            picked_label = labels[0]
            break
    if picked_label is None and option_ids:
        return False, f"{section_id}: crime option not found ({', '.join(option_ids)})"
    await maybe_think_pause(policy)
    await page_reading_pause(page)

    submit = crime_submit_labels(profile) or section_submit_labels(section_id)
    if await click_button_matching(page, submit, policy=policy, dry_run=dry_run):
        detail = f"{section_id} submitted"
        if picked_label:
            detail += f" ({picked_label})"
        return True, detail
    return False, f"{section_id}: Utfør button not found or disabled"


async def _run_stjel_flow(
    page: Page,
    profile: BotProfile,
    *,
    policy: HumanPolicy,
    dry_run: bool,
) -> tuple[bool, str]:
    option_ids = pick_option_ids(profile, "stjel")
    picked_label: str | None = None
    for opt_id in option_ids:
        labels = option_match_labels("stjel", opt_id)
        if await click_option_matching(page, labels, policy=policy, dry_run=dry_run):
            picked_label = labels[0]
            break
    if picked_label is None and option_ids:
        return False, f"stjel: item not found ({', '.join(option_ids)})"
    await maybe_think_pause(policy)
    await page_reading_pause(page)

    mode = crime_steal_target_mode(profile)
    if mode == "specific":
        username = crime_steal_username(profile)
        if not username:
            return False, "stjel: specific target but no username configured"
        if not await fill_murder_target(page, username, policy=policy, dry_run=dry_run):
            return False, f"stjel: could not fill username ({username})"
        await page_reading_pause(page)
        if await click_option_matching(
            page,
            ("jeg vil velge bruker", "velge bruker"),
            policy=policy,
            dry_run=dry_run,
        ):
            await page_reading_pause(page)
    else:
        if await click_option_matching(
            page,
            (
                "stjel fra en tilfeldig bruker",
                "tilfeldig bruker",
                *STEAL_RANDOM_TARGET_LABELS,
            ),
            policy=policy,
            dry_run=dry_run,
        ):
            await page_reading_pause(page)

    submit = crime_submit_labels(profile) or section_submit_labels("stjel")
    if await click_button_matching(page, submit, policy=policy, dry_run=dry_run):
        detail = f"stjel submitted ({picked_label or 'default'}, {mode})"
        return True, detail
    return False, "stjel: Stjel button not found or disabled"


def crime_flow_dry_run_summary(profile: BotProfile) -> str:
    actions = crime_actions_enabled(profile)
    section = pick_crime_section(profile)
    opts = pick_option_ids(profile, section)
    return f"actions={','.join(actions)} next={section} opts={','.join(opts)}"
