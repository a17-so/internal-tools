from fm.render.timeline import build_variation_profile, pick_duration


def test_variation_profile_ranges():
    p = build_variation_profile(42)
    assert 1.01 <= p["zoom"] <= 1.04
    assert 0.985 <= p["speed"] <= 1.015


def test_pick_duration_bounds():
    s, e = pick_duration(0.0, 8.0, 3.0, 5.0)
    assert s == 0.0
    assert 3.0 <= (e - s) <= 5.0
