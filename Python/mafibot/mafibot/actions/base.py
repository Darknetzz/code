"""Action protocol and registry (gameplay actions only — hotel via brain wrapper)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from playwright.async_api import Page

from mafibot.config import BotProfile
from mafibot.human_policy import HumanPolicy
from mafibot.state import GameState


@dataclass
class ActionResult:
    success: bool
    message: str = ""
    cooldown_until: datetime | None = None


class Action(Protocol):
    name: str

    async def can_run(self, state: GameState, profile: BotProfile) -> bool: ...

    async def run(
        self,
        page: Page,
        state: GameState,
        profile: BotProfile,
        policy: HumanPolicy,
        *,
        dry_run: bool = False,
    ) -> ActionResult: ...


def _action_classes() -> tuple[type, ...]:
    from mafibot.actions.combat import MurderAction
    from mafibot.actions.crime import CrimeAction
    from mafibot.actions.economy import BankAction, BusinessAction, DrugsAction, ShipAction, WorkAction
    from mafibot.actions.hospital import HospitalAction
    from mafibot.actions.market import MarketAction
    from mafibot.actions.minions import MinionsAction
    from mafibot.actions.missions import MissionsAction
    from mafibot.actions.organized_crime import OrganizedCrimeAction
    from mafibot.actions.social import FamilyAction, MessagesAction
    from mafibot.actions.travel import TravelAction

    return (
        CrimeAction,
        HospitalAction,
        WorkAction,
        BusinessAction,
        TravelAction,
        ShipAction,
        DrugsAction,
        BankAction,
        MinionsAction,
        MissionsAction,
        OrganizedCrimeAction,
        MarketAction,
        MessagesAction,
        FamilyAction,
        MurderAction,
    )


def all_actions() -> list[Action]:
    return [cls() for cls in _action_classes()]


def action_by_name(name: str) -> Action | None:
    for action in all_actions():
        if action.name == name:
            return action
    return None
