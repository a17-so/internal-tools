from fm.hooks.cooldown import apply_cooldown


def test_apply_cooldown_rejects_active():
    store = {"abc": "2099-01-01T00:00:00+00:00"}
    rows = [{"dedupe_hash": "abc", "url": "https://x"}]
    out = apply_cooldown(rows, store, cooldown_days=21)
    assert out[0]["eligible"] is False
