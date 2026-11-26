import pytest
from labels import normalize_label


@pytest.mark.parametrize(("text", "expected"), [
    ("  Quick   Start  ", "quick start"),
    ("  数据   处理 ABC ", "数据 处理 abc"),
    ("", ""),
])
def test_normalize_label(text, expected):
    assert normalize_label(text) == expected
