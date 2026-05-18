"""Messages and family — rate limited."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, page_reading_pause
from mafibot.navigation import click_button_matching, goto_page
from mafibot.profile_options import family_interval_minutes, messages_interval_minutes
from mafibot.selectors import MESSAGE_REPLY_LABELS
from mafibot.state import GameState

_last_messages_at: datetime | None = None
_last_family_at: datetime | None = None
_messages_this_hour = 0
_hour_started: datetime | None = None


def _social_due(interval_minutes: int, last: datetime | None) -> bool:
    if last is None:
        return True
    return datetime.now() - last >= timedelta(minutes=interval_minutes)


def _can_send_message(profile: BotProfile) -> bool:
    global _messages_this_hour, _hour_started
    limit = profile.messages_max_per_hour
    if limit <= 0:
        return False
    now = datetime.now()
    if _hour_started is None or now - _hour_started > timedelta(hours=1):
        _hour_started = now
        _messages_this_hour = 0
    return _messages_this_hour < limit


class MessagesAction:
    name = "messages"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.social_enabled or state.needs_stop:
            return False
        if profile.messages_only_when_unread:
            return state.unread_messages > 0
        interval = messages_interval_minutes(profile)
        due = _social_due(interval, _last_messages_at)
        return due or state.unread_messages > 0

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        global _last_messages_at, _messages_this_hour
        if dry_run:
            return ActionResult(True, "dry-run: would check messages")

        if not _can_send_message(profile):
            return ActionResult(False, "message rate limit (hourly)")

        await goto_page(page, "messages", policy=policy)
        await page_reading_pause(page)

        open_msg = page.get_by_role("link", name=re.compile(r"les|åpne|innboks", re.I))
        if await open_msg.count() > 0:
            from webbot.human import human_click

            await human_click(page, open_msg.first)

        replied = await click_button_matching(
            page,
            MESSAGE_REPLY_LABELS,
            policy=policy,
        )
        _last_messages_at = datetime.now()
        if replied:
            _messages_this_hour += 1
        return ActionResult(replied or state.unread_messages == 0, "messages checked")


class FamilyAction:
    name = "family"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.social_enabled or state.needs_stop:
            return False
        return _social_due(family_interval_minutes(profile), _last_family_at)

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        global _last_family_at
        if dry_run:
            return ActionResult(True, "dry-run: would check family")

        await goto_page(page, "family", policy=policy)
        await page_reading_pause(page)

        if profile.family_auto_accept:
            accept = page.get_by_role("link", name=re.compile(r"godta|aksepter", re.I))
            if await accept.count() > 0:
                from webbot.human import human_click

                await human_click(page, accept.first)
                _last_family_at = datetime.now()
                return ActionResult(True, "family invite handled")

        _last_family_at = datetime.now()
        return ActionResult(True, "family page visited")
