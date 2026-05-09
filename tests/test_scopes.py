import pytest
from unittest.mock import AsyncMock, patch

from navdoc import NavdocClient, Scope


@pytest.fixture
def client():
    with patch("navdoc.client.NavdocREST"):
        return NavdocClient(api_key="wf_test")


async def test_list_scopes(client):
    client._rest.get = AsyncMock(
        return_value=[
            {"name": "s1", "visibility": "private"},
            {"name": "s2", "visibility": "public"},
        ]
    )
    result = await client.list_scopes()
    client._rest.get.assert_called_once_with("/scopes")
    assert result == [Scope("s1", "private"), Scope("s2", "public")]


async def test_create_scope(client):
    client._rest.post = AsyncMock(return_value={"name": "new-scope", "visibility": "private"})
    result = await client.create_scope("new-scope")
    client._rest.post.assert_called_once_with(
        "/scopes", body={"name": "new-scope", "visibility": "private"}
    )
    assert result == Scope("new-scope", "private")


async def test_create_scope_public(client):
    client._rest.post = AsyncMock(return_value={"name": "pub-scope", "visibility": "public"})
    result = await client.create_scope("pub-scope", visibility="public")
    assert result == Scope("pub-scope", "public")


async def test_get_scope(client):
    client._rest.get = AsyncMock(return_value={"name": "s1", "visibility": "private"})
    result = await client.get_scope("s1")
    client._rest.get.assert_called_once_with("/scopes/s1")
    assert result == Scope("s1", "private")


async def test_update_scope(client):
    client._rest.patch = AsyncMock(return_value={"name": "s1", "visibility": "public"})
    result = await client.update_scope("s1", visibility="public")
    client._rest.patch.assert_called_once_with(
        "/scopes/s1", body={"visibility": "public"}
    )
    assert result == Scope("s1", "public")


async def test_delete_scope(client):
    client._rest.delete = AsyncMock(return_value=None)
    await client.delete_scope("s1")
    client._rest.delete.assert_called_once_with("/scopes/s1")
