# Agent テンプレート

## 概要

`GET /agent-templates` で取得できるプリセットテンプレートを SDK から利用できるようにする。
テンプレートはスター（お気に入り）を付けて管理できる。

## 追加するメソッド

```python
# テンプレート一覧
await client.list_agent_templates()
# -> list[AgentTemplate]

# お気に入り登録
await client.star_agent_template("template_uuid")
# -> None

# お気に入り解除
await client.unstar_agent_template("template_uuid")
# -> None
```

## 追加するモデル

```python
@dataclass
class AgentTemplate:
    id: str
    # その他フィールドは実レスポンス確認後に確定
```

## 対応 REST エンドポイント

| メソッド | パス |
|---|---|
| `GET` | `/agent-templates` |
| `POST` | `/agent-templates/{template_id}/star` |
| `DELETE` | `/agent-templates/{template_id}/star` |

## 優先度

**低** — ユースケースが限定的。Prompt Store 機能（別 issue 検討中）と重複する可能性もある。
