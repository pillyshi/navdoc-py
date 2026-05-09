# Scope 管理 via REST API

## 概要

`NavdocClient` にスコープ（ドキュメントの名前空間）を管理するメソッドを追加する。
現状はスコープを文字列として各メソッドに渡すだけで、CRUD 操作はできない。

## 追加するメソッド

```python
# スコープ一覧
await client.list_scopes()
# -> list[Scope]

# スコープ作成
await client.create_scope("my-scope", visibility="private")
# -> Scope

# スコープ取得
await client.get_scope("my-scope")
# -> Scope

# 公開設定変更
await client.update_scope("my-scope", visibility="public")
# -> Scope

# スコープ削除（中のドキュメントも消えるので要注意）
await client.delete_scope("my-scope")
# -> None
```

## 追加するモデル

```python
@dataclass
class Scope:
    name: str
    visibility: str  # "private" | "public"
```

## 対応 REST エンドポイント

| メソッド | パス |
|---|---|
| `GET` | `/scopes` |
| `POST` | `/scopes` |
| `GET` | `/scopes/{name}` |
| `PATCH` | `/scopes/{name}` |
| `DELETE` | `/scopes/{name}` |
