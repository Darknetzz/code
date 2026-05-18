"""In-game action modules."""

from mafibot.actions.base import Action, ActionResult, all_actions
from mafibot.actions.combat import MurderAction
from mafibot.actions.crime import CrimeAction
from mafibot.actions.economy import BankAction, DrugsAction, HotelAction, ShipAction, WorkAction
from mafibot.actions.social import FamilyAction, MessagesAction
from mafibot.actions.travel import TravelAction

__all__ = [
    "Action",
    "ActionResult",
    "all_actions",
    "CrimeAction",
    "TravelAction",
    "WorkAction",
    "HotelAction",
    "ShipAction",
    "DrugsAction",
    "BankAction",
    "MurderAction",
    "MessagesAction",
    "FamilyAction",
]
