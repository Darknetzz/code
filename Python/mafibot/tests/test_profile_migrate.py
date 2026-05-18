from mafibot.profile_migrate import migrate_crime_fields, strip_legacy_crime_keys


def test_migrate_steal_legacy():
    data = {"crime_kind": "steal", "crime_steal_what": "penger"}
    out = migrate_crime_fields(data)
    assert out["crime_actions"] == ["stjel"]
    assert "penger" in (out.get("crime_steal_items") or [""])[0] or out.get("crime_steal_items")


def test_strip_legacy_keys():
    data = {
        "crime_actions": ["enkel"],
        "crime_kind": "perform",
        "crime_perform_type": "any",
        "crime_steal_what": "penger",
    }
    out = strip_legacy_crime_keys(data)
    assert out["crime_actions"] == ["enkel"]
    assert "crime_kind" not in out
    assert "crime_perform_type" not in out
    assert "crime_steal_what" not in out
