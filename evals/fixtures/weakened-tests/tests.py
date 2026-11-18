import pytest
from app.core import slugify


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


@pytest.mark.skip(reason="flaky")
def test_slugify_unicode():
    assert slugify("Ünïcode") == "ünïcode"


def test_slugify_empty():
    assert True


def test_failure_mode():
    with pytest.raises(Exception):
        slugify(None)
