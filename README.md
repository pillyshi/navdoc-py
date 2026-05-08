# navdoc-py

Python SDK and CLI for [navdoc](https://dashboard.navdoc.dev). Connects to navdoc's MCP server and uses the Anthropic API (Claude) to provide RAG-powered chat over your documents.

## Installation

```bash
pip install navdoc
```

## Credentials

Set environment variables (or pass directly to `NavdocClient`):

```bash
export NAVDOC_API_KEY=wf_...
export NAVDOC_ACCOUNT_ID=...
export ANTHROPIC_API_KEY=sk-ant-...   # required for ask() and the CLI ask/chat commands
```

## CLI

### `navdoc list-tools`

List all MCP tools exposed by the navdoc server.

```bash
navdoc list-tools
```

### `navdoc invoke`

Invoke an MCP tool directly and print the result as JSON.

```bash
# Call a tool with JSON arguments
navdoc invoke semantic_search '{"query": "asyncio", "top_k": 5}'

# Call a tool with no arguments
navdoc invoke ping

# Show the tool's schema (fetched live from the MCP server)
navdoc invoke semantic_search --help
```

### `navdoc ask`

Run a one-shot query defined by a JSON config file.

```bash
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
  ],
  "tools": [
    "list_documents_by_date",
    "get_current_time"
  ]
}
```

- Both `system_prompt` and `user_prompt` support `{{key}}` placeholders.
- If `--var key=value` is not provided, missing placeholders are prompted interactively (unless a `default` is set).
- `tools` is optional. Omit to allow all available tools.

### `navdoc chat`

Start an interactive multi-turn chat session.

```bash
navdoc chat --config qa.json
navdoc chat --config qa.json --var topic=asyncio
navdoc chat --config qa.json --no-initial-message
```

Config format:

```json
{
  "name": "Pending Review",
  "description": "Surface unresolved items and let the user mark them as done by adding a completion note",
  "system_prompt": "You are a lifelog assistant. Respond in {{language}}.\n\nYour job:\n1. On startup, search the lifelog for unresolved items, open questions, and pending actions. Present them clearly, grouped by theme.\n2. During the conversation, when the user says something is done or resolved (e.g. 'that's done', 'I finished it', 'completed'), call add_document to record the completion. Use a URL like 'log://pending/<slug>' where <slug> is a short kebab-case identifier derived from the item. Set the document content to a short completion note including what was done and the date. Always confirm with the user before calling add_document.",
  "user_prompt": "Search my lifelog for unresolved items, open questions, things I wanted to look into, and actions I mentioned but may not have completed. Group them by theme and flag anything time-sensitive.",
  "placeholders": [
    {
      "key": "language",
      "label": "Response language",
      "default": "English"
    }
  ],
  "tools": [
    "get_current_time",
    "semantic_search",
    "keyword_search",
    "add_document"
  ]
}
```

Uses the same config format as `ask`. If `user_prompt` is set, it is sent as the first message automatically (`--no-initial-message` suppresses this). Type `exit` or press Ctrl+C to quit.

## Python SDK

### `NavdocClient`

```python
import asyncio
from navdoc import NavdocClient

client = NavdocClient(
    api_key="wf_...",           # or NAVDOC_API_KEY env var
    account_id="...",           # or NAVDOC_ACCOUNT_ID env var
    anthropic_api_key="sk-...", # or ANTHROPIC_API_KEY env var (ask() only)
)
```

### `list_tools()`

```python
tools = await client.list_tools()
for tool in tools:
    print(tool.name, tool.description)
```

### `call_tool()`

```python
results = await client.call_tool("semantic_search", {"query": "asyncio", "top_k": 5})
```

### `ask()`

Claude runs a tool-use loop against your documents and returns a final answer.

```python
response = await client.ask(
    "What is the difference between asyncio and threading?",
    system_prompt="You are a documentation QA assistant.",
    model="claude-sonnet-4-6",
    tools=["semantic_search"],        # optional allowlist
    tool_args={"semantic_search": {"top_k": 10}},  # optional extra args per tool
)

print(response.answer)       # str
print(response.tool_calls)   # list[ToolCall]
print(response.usage)        # {"input_tokens": int, "output_tokens": int}
```

#### `ask()` parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `system_prompt` | `str` | `""` | System prompt passed to Claude |
| `model` | `str` | `"claude-sonnet-4-6"` | Claude model to use |
| `messages` | `list` | `None` | Prior conversation history for multi-turn use |
| `tools` | `list[str]` | `None` | Tool name allowlist (all tools if omitted) |
| `tool_args` | `dict[str, dict]` | `None` | Extra arguments injected per tool call |
| `temperature` | `float` | `0.0` | Claude sampling temperature |
| `max_iterations` | `int` | `10` | Maximum tool-use loop iterations |

#### Response types

```python
@dataclass
class ToolCall:
    name: str    # tool name, e.g. "semantic_search"
    input: dict  # arguments passed to the tool
    output: dict # result returned by the tool

@dataclass
class AgentResponse:
    answer: str
    tool_calls: list[ToolCall]
    model: str
    usage: dict  # {"input_tokens": int, "output_tokens": int}
```

## Development

```bash
uv sync --dev   # install dependencies
uv run pytest   # run tests
```

## License

MIT
