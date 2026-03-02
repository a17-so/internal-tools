from fm.validate.manifest import validate_manifest_data


def test_manifest_requires_styles():
    errors, warnings = validate_manifest_data({})
    assert errors
    assert isinstance(warnings, list)


def test_manifest_valid_minimal():
    data = {
        "timing": {"hook_seconds_min": 3, "hook_seconds_max": 5},
        "styles": {
            "calm_reclaim": {"clip_pools": [], "overlays": {"top_bar": {}}},
            "intense_smart": {"clip_pools": [], "overlays": {"top_bar": {}}},
        },
    }
    errors, _ = validate_manifest_data(data)
    assert errors == []
