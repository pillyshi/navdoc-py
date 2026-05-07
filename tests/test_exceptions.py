import pytest
from navdoc.exceptions import (
    NavdocError,
    AuthError,
    MissingAnthropicKeyError,
    MCPError,
    MaxIterationsError,
)


def test_hierarchy():
    assert issubclass(AuthError, NavdocError)
    assert issubclass(MissingAnthropicKeyError, NavdocError)
    assert issubclass(MCPError, NavdocError)
    assert issubclass(MaxIterationsError, NavdocError)


def test_mcp_error_stores_original():
    original = ValueError("original")
    err = MCPError("wrapped", original=original)
    assert err.original is original
    assert "wrapped" in str(err)


def test_max_iterations_error_stores_count():
    err = MaxIterationsError(5)
    assert err.iterations == 5
    assert "5" in str(err)


def test_raise_catch():
    with pytest.raises(NavdocError):
        raise AuthError("401")

    with pytest.raises(MissingAnthropicKeyError):
        raise MissingAnthropicKeyError("no key")
