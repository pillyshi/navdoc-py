import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from navdoc import AgentTool, NavdocClient
from navdoc.cli import app
from typer.testing import CliRunner

runner = CliRunner()


# --- NavdocClient.list_tools() ---

@pytest.fixture
def client():
    with patch("navdoc.client.NavdocREST"):
        c = NavdocClient(api_key="wf_test")
    return c


@pytest.mark.asyncio
async def test_list_tools_returns_agent_tools(client):
    client._rest.get = AsyncMock(return_value=[
        {"name": "semantic_search", "description": "Search docs", "inputSchema": {"type": "object"}},
        {"name": "add_document", "description": "Add a doc", "inputSchema": {}},
    ])

    tools = await client.list_tools()

    assert len(tools) == 2
    assert tools[0] == AgentTool(name="semantic_search", description="Search docs", input_schema={"type": "object"})
    assert tools[1] == AgentTool(name="add_document", description="Add a doc", input_schema={})


@pytest.mark.asyncio
async def test_list_tools_empty(client):
    client._rest.get = AsyncMock(return_value=[])
    tools = await client.list_tools()
    assert tools == []


@pytest.mark.asyncio
async def test_list_tools_missing_fields(client):
    client._rest.get = AsyncMock(return_value=[{"name": "my_tool"}])
    tools = await client.list_tools()
    assert tools[0].name == "my_tool"
    assert tools[0].description == ""
    assert tools[0].input_schema == {}


# --- navdoc tools CLI command ---

def make_tools_client(tools: list[AgentTool]):
    async def _list_tools():
        return tools

    client = MagicMock()
    client.list_tools = _list_tools
    return client


def test_tools_cmd_displays_table():
    mock_client = make_tools_client([
        AgentTool(name="semantic_search", description="Search documents"),
        AgentTool(name="add_document", description="Add a document"),
    ])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["tools"])
    assert result.exit_code == 0
    assert "semantic_search" in result.output
    assert "add_document" in result.output


def test_tools_cmd_empty():
    mock_client = make_tools_client([])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["tools"])
    assert result.exit_code == 0
    assert "No tools" in result.output
