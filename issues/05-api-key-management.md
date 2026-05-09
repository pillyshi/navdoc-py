# API キー管理

## 概要

navdoc API キーの一覧・作成・削除をプログラムから行えるようにする。
マルチテナント構成や CI/CD でのキーローテーションに使える。

## 追加するメソッド

```python
# キー一覧
await client.list_api_keys()
# -> list[APIKey]

# キー作成（invoke_only=True にすると ask() 専用の read-only キーになる）
await client.create_api_key("ci-key", scope="my-scope", invoke_only=True)
# -> APIKey（api_key フィールドは作成時のみ返る）

# キー削除
await client.delete_api_key("key_id_xxx")
# -> None
```

## 追加するモデル

```python
@dataclass
class APIKey:
    id: str
    name: str
    key_prefix: str
    api_key: str | None  # 作成時のみ、以降は None
```

## 対応 REST エンドポイント

| メソッド | パス |
|---|---|
| `GET` | `/api-keys` |
| `POST` | `/api-keys` |
| `DELETE` | `/api-keys/{key_id}` |

## 優先度

**低** — ダッシュボード的な管理機能。ユーザーが直接使うユースケースは少ない。
