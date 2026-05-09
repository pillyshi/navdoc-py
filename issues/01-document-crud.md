# Document CRUD via REST API

## 概要

`NavdocClient` に REST API (`https://api.navdoc.dev`) 経由でドキュメントを管理するメソッドを追加する。
現在は MCP 経由の RAG 検索のみで、ドキュメントの投入・管理は SDK からできない。

## 追加するメソッド

```python
# ドキュメント一覧取得
await client.list_documents(scope="my-scope", limit=50, offset=0)
# -> list[Document]

# ドキュメント投入（テキストをそのまま渡す）
await client.upload_document(
    content="...",
    url="https://example.com/page",
    scope="my-scope",
)
# -> Document(document_id="...", chunk_count=3)

# チャンク単位で投入（既に分割済みのケース）
await client.upload_chunks(
    chunks=["chunk1", "chunk2"],
    document_url="https://example.com/page",
    scope="my-scope",
)
# -> list[str]  # chunk_ids

# ドキュメント削除
await client.delete_document("doc_id_xxx")
# -> None
```

## 実装方針

- `navdoc/rest.py` に `NavdocREST` クラスを新設（httpx 非同期クライアント）
- `NavdocClient.__init__` で `NavdocREST` を初期化
- `navdoc/models.py` に `Document` dataclass を追加
- `__init__.py` から `Document` をエクスポート

## 対応 REST エンドポイント

| メソッド | パス | 用途 |
|---|---|---|
| `GET` | `/documents` | 一覧取得（query: scope, limit, offset） |
| `POST` | `/documents` | 投入（body: content, url, scope, created_at） |
| `POST` | `/documents/chunks` | チャンク投入（body: chunks, document_url, scope） |
| `DELETE` | `/documents/{document_id}` | 削除 |
