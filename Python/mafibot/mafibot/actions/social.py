"""Messages and family — rate limited."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from playwright.async_api import Page

from mafibot.actions.base import ActionResult
from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy, between_actions, page_reading_pause
from mafibot.navigation import click_button_matching, goto_side
from mafibot.selectors import MESSAGE_REPLY_LABELS
from mafibot.state import GameState

_last_messages_at: datetime | None = None
_last_family_at: datetime | None = None
_messages_this_hour = 0
_hour_started: datetime | None = None

MAX_MESSAGES_PER_HOUR = 8


def _social_due(profile: BotProfile, last: datetime | None) -> bool:
    if last is None:
        return True
    return datetime.now() - last >= timedelta(minutes=profile.social_interval_minutes)


def _can_send_message() -> bool:
    global _messages_this_hour, _hour_started
    now = datetime.now()
    if _hour_started is None or now - _hour_started > timedelta(hours=1):
        _hour_started = now
        _messages_this_hour = 0
    return _messages_this_hour < MAX_MESSAGES_PER_HOUR


class MessagesAction:
    name = "messages"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.social_enabled or state.needs_stop:
            return False
        if state.unread_messages <= 0 and not _social_due(profile, _last_messages_at):
            return False
        return _social_due(profile, _last_messages_at) or state.unread_messages > 0

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

        if not _can_send_message():
            return ActionResult(False, "message rate limit (hourly)")

        await goto_side(page, "messages", policy=policy)
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
        await between_actions(page, policy)
        return ActionResult(replied or state.unread_messages == 0, "messages checked")


class FamilyAction:
    name = "family"

    async def can_run(self, state: GameState, profile: BotProfile) -> bool:
        if not profile.social_enabled or state.needs_stop:
            return False
        return _social_due(profile, _last_family_at)

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

        await goto_side(page, "family", policy=policy)
        await page_reading_pause(page)

        accept = page.get_by_role("link", name=re.compile(r"godta|aksepter", re.I))
        if await accept.count() > 0:
            from webbot.human import human_click

            await human_click(page, accept.first)
            _last_family_at = datetime.now()
            await between_actions(page, policy)
            return ActionResult(True, "family invite handled")

        _last_family_at = datetime.now()
        await between_actions(page, policy)
        return ActionResult(True, "family page visited")
