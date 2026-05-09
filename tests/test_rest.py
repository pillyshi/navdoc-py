import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from navdoc.rest import NavdocREST
from navdoc.exceptions import AuthError, NavdocError


def make_response(status_code: int, json_data=None, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


async def test_get_success():
    rest = NavdocREST("wf_test")
    mock_resp = make_response(200, [{"document_id": "d1", "chunk_count": 2}])
    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        result = await rest.get("/documents", params={"scope": "s1"})
    assert result == [{"document_id": "d1", "chunk_count": 2}]


async def test_post_success():
    rest = NavdocREST("wf_test")
    mock_resp = make_response(200, {"document_id": "d_new", "chunk_count": 3})
    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await rest.post("/documents", body={"content": "text", "url": "http://x.com"})
    assert result == {"document_id": "d_new", "chunk_count": 3}


async def test_delete_success():
    rest = NavdocREST("wf_test")
    mock_resp = make_response(204)
    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.delete = AsyncMock(return_value=mock_resp)
        await rest.delete("/documents/doc1")


async def test_raises_auth_error_on_401():
    rest = NavdocREST("wf_bad")
    mock_resp = make_response(401, text="Unauthorized")
    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        with pytest.raises(AuthError):
            await rest.get("/documents")


async def test_raises_navdoc_error_on_500():
    rest = NavdocREST("wf_test")
    mock_resp = make_response(500, text="Internal Server Error")
    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        with pytest.raises(NavdocError):
            await rest.get("/documents")


async def test_patch_success():
    rest = NavdocREST("wf_test")
    mock_resp = make_response(200, {"name": "s1", "visibility": "public"})
    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.patch = AsyncMock(return_value=mock_resp)
        result = await rest.patch("/scopes/s1", body={"visibility": "public"})
    assert result == {"name": "s1", "visibility": "public"}


async def test_none_params_excluded():
    rest = NavdocREST("wf_test")
    mock_resp = make_response(200, [])
    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        mock_get = AsyncMock(return_value=mock_resp)
        MockClient.return_value.__aenter__.return_value.get = mock_get
        await rest.get("/documents", params={"scope": None, "limit": 50})
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"limit": 50}
