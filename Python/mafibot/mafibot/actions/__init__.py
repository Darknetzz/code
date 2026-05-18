"""In-game action modules."""

from mafibot.actions.base import Action, ActionResult, all_actions
from mafibot.actions.combat import MurderAction
from mafibot.actions.crime import CrimeAction
from mafibot.actions.economy import BankAction, BusinessAction, DrugsAction, ShipAction
from mafibot.actions.hotel_book import BookHotelAction
from mafibot.actions.hotel_leave import LeaveHotelAction
from mafibot.actions.social import FamilyAction, MessagesAction
from mafibot.actions.travel import TravelAction

__all__ = [
    "Action",
    "ActionResult",
    "all_actions",
    "BookHotelAction",
    "LeaveHotelAction",
    "CrimeAction",
    "BusinessAction",
    "TravelAction",
    "ShipAction",
    "DrugsAction",
    "BankAction",
    "MurderAction",
    "MessagesAction",
    "FamilyAction",
]
