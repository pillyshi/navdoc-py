import pytest
from unittest.mock import patch

from navdoc import NavdocClient


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("NAVDOC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="api_key"):
        NavdocClient(api_key="")


def test_env_var_fallback(monkeypatch):
    monkeypatch.setenv("NAVDOC_API_KEY", "wf_env")
    with patch("navdoc.client.NavdocREST"):
        client = NavdocClient()
    assert client._api_key == "wf_env"


def test_explicit_api_key(monkeypatch):
    monkeypatch.delenv("NAVDOC_API_KEY", raising=False)
    with patch("navdoc.client.NavdocREST"):
        client = NavdocClient(api_key="wf_explicit")
    assert client._api_key == "wf_explicit"
