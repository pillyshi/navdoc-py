# navdoc-py

Python SDK for [navdoc](https://navdoc.dev). Combines navdoc's MCP server with the Anthropic API (Claude) to provide both low-level MCP tool wrappers and a high-level RAG chat interface.

## Installation

```bash
pip install navdoc
```

## Setup

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```
NAVDOC_API_KEY=wf_...
NAVDOC_ACCOUNT_ID=...
ANTHROPIC_API_KEY=sk-ant-...
```

Credentials can also be passed directly to `NavdocClient`.

## Usage

### Low-level API

Only a navdoc API key is required.

```python
import asyncio
from navdoc import NavdocClient

async def main():
    client = NavdocClient(api_key="wf_...", account_id="...")

    # Search documents
    results = await client.search("Python asyncio", top_k=5)
    print(results)

    # Fetch a document by URL
    doc = await client.get_document(url="https://...")
    print(doc)

asyncio.run(main())
```

### High-level API (`ask`)

Requires an Anthropic API key in addition to the navdoc API key. Claude uses navdoc's MCP tools in a tool-use loop to answer questions based on your documents.

```python
import asyncio
from navdoc import NavdocClient

async def main():
    client = NavdocClient(
        api_key="wf_...",
        account_id="...",
        anthropic_api_key="sk-ant-...",  # or set ANTHROPIC_API_KEY env var
    )

    response = await client.ask(
        "What is the difference between asyncio and threading?",
        system_prompt="You are a documentation QA assistant.",
        model="claude-sonnet-4-6",
        top_k=5,
    )

    print(response.answer)
    print(response.tool_calls)  # list of MCP tool calls made during the loop
    print(response.usage)       # {"input_tokens": ..., "output_tokens": ...}

asyncio.run(main())
```

### `ask()` parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `system_prompt` | `str` | `""` | System prompt passed to Claude |
| `model` | `str` | `"claude-sonnet-4-6"` | Claude model to use |
| `top_k` | `int` | `5` | Number of search results to retrieve |
| `temperature` | `float` | `0.0` | Claude sampling temperature |
| `max_iterations` | `int` | `10` | Maximum tool-use loop iterations |

### Response types

```python
@dataclass
class ToolCall:
    name: str    # e.g. "search"
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
# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Build
uv run python -m build

# Publish to PyPI
uv run twine upload dist/*
```

## License

MIT
