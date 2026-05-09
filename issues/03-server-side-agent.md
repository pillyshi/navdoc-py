# サーバーサイド Agent (POST /agent)

## 概要

navdoc REST API の `POST /agent` を使い、Anthropic API key 不要で RAG チャットを実行できる
メソッドを追加する。現在の `ask()` はユーザーが Anthropic API key を持っている前提だが、
このエンドポイントはサーバー側で LLM を動かすため key 不要になる可能性がある。

## 検討事項

- レスポンス型が OpenAPI spec 上 "Generic object" で不明。実装前に実際のレスポンスを確認する必要あり
- streaming 対応しているかも要確認
- `ask()` の代替として同じシグネチャにするか、別メソッド `ask_server()` にするかを決める
- 既存の `ask()` で使う `AgentResponse`（tool_calls 等）が返ってくるかは不明

## 想定インターフェース

```python
await client.ask_server(
    "質問",
    scope="my-scope",
    system_prompt="...",
)
# -> AgentResponse (または新しい型)
```

## 対応 REST エンドポイント

| メソッド | パス | リクエスト body |
|---|---|---|
| `POST` | `/agent` | `{messages, scope, timezone, system_prompt}` |

## 優先度

**中** — 実レスポンスの確認が先決。Anthropic key 不要というメリットは大きいが、
`ask()` との機能差・出力形式が不明な状態では設計できない。
