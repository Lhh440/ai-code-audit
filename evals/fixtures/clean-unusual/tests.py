import pytest


def find(items, needle):
    return next((item for item in items if item is needle), None)


def test_missing_returns_none():
    assert find([1, 2], 3) is None
    assert find([1, 2], 2) is not None


def test_specific_failure():
    with pytest.raises(ValueError):
        int("not a number")


def test_open_with_explicit_text_mode(tmp_path):
    path = tmp_path / "x"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x")
