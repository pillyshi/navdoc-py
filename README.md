# navdoc-py

Python SDK and CLI for [navdoc](https://dashboard.navdoc.dev). Upload and manage your documents via the navdoc REST API, and run RAG-powered chat with Claude.

## Installation

```bash
pip install navdoc
```

## Credentials

```bash
export NAVDOC_API_KEY=wf_...
```

## CLI

### `navdoc ask`

Run a one-shot query.

```bash
# Direct question
navdoc ask "What is asyncio?"
navdoc ask "What is asyncio?" --system-prompt "Be concise."

# Config-based
navdoc ask --config daily.json
navdoc ask --config daily.json --var date=2025-05-08
```

Config format:

```json
{
  "name": "Daily Summary",
  "description": "Summarize a day's lifelog entries with activity count and time-of-day trends",
  "system_prompt": "You are a lifelog analyst. Respond in {{language}}.",
  "user_prompt": "Please summarize the logs for {{date}}. Include the number of activities and time-of-day trends.",
  "placeholders": [
    {
      "key": "date",
      "label": "Target date",
      "default": "today"
    },
    {
      "key": "language",
      "label": "Response language",
      "default": "English"
    }
  ]
}
```

- Both `system_prompt` and `user_prompt` support `{{key}}` placeholders.
- If `--var key=value` is not provided, missing placeholders are prompted interactively (unless a `default` is set).

### `navdoc chat`

Start an interactive multi-turn chat session.

```bash
# No config — plain chat
navdoc chat

# With a system prompt
navdoc chat --system-prompt "You are a helpful assistant."

# With a config file
navdoc chat --config qa.json
navdoc chat --config qa.json --var topic=asyncio
navdoc chat --config qa.json --no-initial-message
```

`--config` is optional. If omitted, chat starts immediately with an empty (or `--system-prompt`-specified) prompt. If `user_prompt` is set in the config, it is sent as the first message automatically (`--no-initial-message` suppresses this). Type `exit` or press Ctrl+C to quit.

## Python SDK

### `NavdocClient`

```python
from navdoc import NavdocClient

client = NavdocClient(
    api_key="wf_...",  # or NAVDOC_API_KEY env var
)
```

### Document management

Upload, list, and delete documents via the navdoc REST API.

#### `upload_document()`

```python
from navdoc import NavdocClient, Document

doc = await client.upload_document(
    "Full text content of the document...",
    url="https://example.com/page",   # unique identifier for the document
    scope="my-scope",                 # optional
)
print(doc.document_id)  # str
print(doc.chunk_count)  # int
```

#### `upload_chunks()`

Upload pre-split chunks instead of raw text (useful when you handle chunking yourself).

```python
chunk_ids = await client.upload_chunks(
    ["First chunk...", "Second chunk..."],
    document_url="https://example.com/page",
    scope="my-scope",
)
```

#### `list_documents()`

```python
docs = await client.list_documents(scope="my-scope", limit=50, offset=0)
for doc in docs:
    print(doc.document_id, doc.chunk_count)
```

#### `delete_document()`

```python
await client.delete_document("doc_id_xxx")
```

#### `Document` type

```python
@dataclass
class Document:
    document_id: str
    chunk_count: int
```

### Scope management

Scopes are namespaces that group documents.

```python
from navdoc import NavdocClient, Scope

scopes = await client.list_scopes()
scope = await client.create_scope("my-scope", visibility="private")
scope = await client.get_scope("my-scope")
scope = await client.update_scope("my-scope", visibility="public")
await client.delete_scope("my-scope")  # also removes all documents inside
```

#### `Scope` type

```python
@dataclass
class Scope:
    name: str
    visibility: str  # "private" | "public"
```

### Server-side agent

RAG chat powered by navdoc's built-in Claude agent.

#### `stream()` — streaming

Yields `StreamEvent` objects as the server sends them.

```python
from navdoc import NavdocClient, StreamEvent

async for event in client.stream(
    "What is asyncio?",
    system_prompt="Answer concisely.",
    timezone="Asia/Tokyo",
):
    if event.type == "text":
        print(event.delta, end="", flush=True)
```

#### `ask_server()` — non-streaming

Collects the full response and returns an `AgentResponse`.

```python
response = await client.ask_server(
    "What is asyncio?",
    messages=[{"role": "user", "content": "previous turn"}, ...],  # optional history
    system_prompt="Answer concisely.",
    timezone="Asia/Tokyo",
)
print(response.answer)
print(response.tool_calls)
```

#### `StreamEvent` type

```python
@dataclass
class StreamEvent:
    type: str        # "text" | "tool_use" | "tool_result" | "done" | "error"
    delta: str | None = None    # type=text
    name: str | None = None     # type=tool_use, tool_result
    input: dict | None = None   # type=tool_use, tool_result
    message: str | None = None  # type=error
```

## Development

```bash
uv sync --dev   # install dependencies
uv run pytest   # run tests
```

## License

MIT
