from reuse_target import normalize_label


def test_reused_whitespace():
    assert normalize_label("  X   Y ") == "x y"
