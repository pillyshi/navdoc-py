import pytest
from mcp import types as mcp_types


@pytest.fixture
def mock_mcp_tools() -> list[mcp_types.Tool]:
    return [
        mcp_types.Tool(
            name="search",
            description="Search documents",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                },
                "required": ["query"],
            },
        ),
        mcp_types.Tool(
            name="get_document",
            description="Get a document by URL",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        ),
    ]


@pytest.fixture
def mock_search_result() -> mcp_types.CallToolResult:
    return mcp_types.CallToolResult(
        content=[
            mcp_types.TextContent(
                type="text",
                text='[{"title": "Doc 1", "content": "Python asyncio basics"}]',
            )
        ]
    )


@pytest.fixture
def mock_get_document_result() -> mcp_types.CallToolResult:
    return mcp_types.CallToolResult(
        content=[
            mcp_types.TextContent(
                type="text",
                text='{"title": "Doc 1", "content": "Full document content here"}',
            )
        ]
    )
