"""In-game action modules."""

from __future__ import annotations

from mafibot.actions.base import Action, ActionResult, all_actions
from mafibot.actions.combat import MurderAction
from mafibot.actions.crime import CrimeAction
from mafibot.actions.economy import BankAction, BusinessAction, DrugsAction, ShipAction
from mafibot.actions.hospital import HospitalAction
from mafibot.actions.hotel_book import BookHotelAction
from mafibot.actions.hotel_leave import LeaveHotelAction
from mafibot.actions.market import MarketAction
from mafibot.actions.minions import MinionsAction
from mafibot.actions.missions import MissionsAction
from mafibot.actions.organized_crime import OrganizedCrimeAction
from mafibot.actions.social import FamilyAction, MessagesAction
from mafibot.actions.travel import TravelAction

__all__ = [
    "Action",
    "ActionResult",
    "all_actions",
    "BookHotelAction",
    "LeaveHotelAction",
    "CrimeAction",
    "HospitalAction",
    "BusinessAction",
    "TravelAction",
    "ShipAction",
    "DrugsAction",
    "BankAction",
    "MurderAction",
    "MessagesAction",
    "FamilyAction",
    "MinionsAction",
    "MissionsAction",
    "OrganizedCrimeAction",
    "MarketAction",
]
