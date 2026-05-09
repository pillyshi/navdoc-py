import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from navdoc import NavdocClient, Document


@pytest.fixture
def client():
    with patch("navdoc.client.NavdocTools"), patch("navdoc.client.NavdocREST"):
        return NavdocClient(api_key="wf_test", account_id="acc_test")


async def test_list_documents_list_response(client):
    client._rest.get = AsyncMock(
        return_value=[
            {"document_id": "doc1", "chunk_count": 3},
            {"document_id": "doc2", "chunk_count": 1},
        ]
    )
    result = await client.list_documents(scope="my-scope")
    client._rest.get.assert_called_once_with(
        "/documents", params={"scope": "my-scope", "limit": 50, "offset": 0}
    )
    assert result == [Document("doc1", 3), Document("doc2", 1)]


async def test_list_documents_dict_with_items(client):
    client._rest.get = AsyncMock(
        return_value={"items": [{"document_id": "doc1", "chunk_count": 2}]}
    )
    result = await client.list_documents()
    assert result == [Document("doc1", 2)]


async def test_upload_document(client):
    client._rest.post = AsyncMock(return_value={"document_id": "doc_new", "chunk_count": 5})
    result = await client.upload_document(
        "Hello world", url="https://example.com/page", scope="s1"
    )
    client._rest.post.assert_called_once_with(
        "/documents",
        body={"content": "Hello world", "url": "https://example.com/page", "scope": "s1", "created_at": None},
    )
    assert result == Document("doc_new", 5)


async def test_upload_chunks(client):
    client._rest.post = AsyncMock(return_value={"chunk_ids": ["c1", "c2"]})
    result = await client.upload_chunks(
        ["chunk1", "chunk2"], document_url="https://example.com/page", scope="s1"
    )
    client._rest.post.assert_called_once_with(
        "/documents/chunks",
        body={"chunks": ["chunk1", "chunk2"], "document_url": "https://example.com/page", "scope": "s1"},
    )
    assert result == ["c1", "c2"]


async def test_delete_document(client):
    client._rest.delete = AsyncMock(return_value=None)
    await client.delete_document("doc_abc")
    client._rest.delete.assert_called_once_with("/documents/doc_abc")
