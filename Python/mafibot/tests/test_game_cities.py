from mafibot.game_cities import GAME_CITIES


def test_game_cities_includes_map_cities():
    names = set(GAME_CITIES)
    assert "Kabul" in names
    assert "London" in names
    assert "Rio" in names
    assert "Kuala Lumpur" in names
    assert len(GAME_CITIES) == 9
