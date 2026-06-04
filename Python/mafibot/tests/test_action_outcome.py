"""Parse action outcome text from game pages."""

from __future__ import annotations

from mafibot.action_outcome import parse_action_outcome


def test_parse_money_and_rank() -> None:
    text = "Du fikk 12 500 kr og tjente 3 rankpoeng for handlingen."
    hints = parse_action_outcome(text)
    assert hints.money_delta == 12500
    assert hints.rank_delta == 3


def test_parse_grams_sold() -> None:
    text = "Du solgte 25 gram cannabis og 10 gram opium i byen."
    hints = parse_action_outcome(text)
    assert hints.cannabis_grams == 25
    assert hints.opium_grams == 10


def test_parse_money_loss() -> None:
    text = "Du betalt 2 000 kr for behandling."
    hints = parse_action_outcome(text)
    assert hints.money_delta == -2000
