from mafibot.config import BotProfile
from mafibot.crime_catalog import pick_crime_section, reset_indices
from mafibot.rotation import reset_rotation_state


def test_reset_rotation_state():
    profile = BotProfile(crime_actions=["enkel", "tung"], crime_rotate_actions=True)
    first = pick_crime_section(profile)
    second = pick_crime_section(profile)
    reset_rotation_state()
    again = pick_crime_section(profile)
    assert first == "enkel"
    assert second == "tung"
    assert again == "enkel"
