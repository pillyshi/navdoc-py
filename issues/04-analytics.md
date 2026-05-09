# Analytics エンドポイント

## 概要

クエリログと使用量統計を取得するメソッドを追加する。
ダッシュボード・監視用途や、どんな質問がよく来るかの分析に使える。

## 追加するメソッド

```python
# 過去のクエリ履歴
await client.list_queries(scope="my-scope", days=30, limit=50)
# -> list[QueryLog]  (スキーマは要確認)

# 使用量統計（トークン数・リクエスト数など）
await client.get_usage()
# -> list[UsageStat]  (スキーマは要確認)
```

## 追加するモデル

OpenAPI spec 上レスポンスが "Array of objects" のみで詳細不明。
実装前に実際のレスポンスを確認してモデルを定義する。

## 対応 REST エンドポイント

| メソッド | パス | クエリパラメータ |
|---|---|---|
| `GET` | `/analytics/queries` | limit (1-200), scope, days (1-365, default 30) |
| `GET` | `/analytics/usage` | なし |
