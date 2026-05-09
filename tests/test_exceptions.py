import pytest
from navdoc.exceptions import NavdocError, AuthError


def test_hierarchy():
    assert issubclass(AuthError, NavdocError)


def test_raise_catch():
    with pytest.raises(NavdocError):
        raise AuthError("401")
