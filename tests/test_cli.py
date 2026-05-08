import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types as mcp_types
from typer.testing import CliRunner

from navdoc.cli import app

runner = CliRunner()


def make_mock_client(call_tool_result=None, list_tools_result=None):
    client = MagicMock()
    client.call_tool = AsyncMock(return_value=call_tool_result if call_tool_result is not None else [])
    client.list_tools = AsyncMock(return_value=list_tools_result if list_tools_result is not None else [])
    return client


@pytest.fixture
def mock_tools():
    return [
        mcp_types.Tool(
            name="semantic_search",
            description="Search documents semantically",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
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


# --- A: 正常系 ---

def test_invoke_with_json_args():
    mock_client = make_mock_client(call_tool_result=[{"text": "result"}])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search", '{"query": "foo"}'])
    assert result.exit_code == 0
    assert "result" in result.output
    mock_client.call_tool.assert_called_once_with("semantic_search", {"query": "foo"})


def test_invoke_without_args():
    mock_client = make_mock_client(call_tool_result=[{"text": "ok"}])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search"])
    assert result.exit_code == 0
    mock_client.call_tool.assert_called_once_with("semantic_search", {})


def test_invoke_empty_result():
    mock_client = make_mock_client(call_tool_result=[])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search"])
    assert result.exit_code == 0
    assert "[]" in result.output


# --- B: 動的ヘルプ ---

def test_invoke_help_shows_description(mock_tools):
    mock_client = make_mock_client(list_tools_result=mock_tools)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search", "--help"])
    assert result.exit_code == 0
    assert "Search documents semantically" in result.output


def test_invoke_help_shows_parameters(mock_tools):
    mock_client = make_mock_client(list_tools_result=mock_tools)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search", "--help"])
    assert result.exit_code == 0
    assert "query" in result.output
    assert "required" in result.output
    assert "top_k" in result.output
    assert "optional" in result.output


def test_invoke_help_tool_not_found(mock_tools):
    mock_client = make_mock_client(list_tools_result=mock_tools)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "nonexistent_tool", "--help"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_invoke_help_no_properties():
    tools = [
        mcp_types.Tool(
            name="ping",
            description="Ping the server",
            inputSchema={"type": "object"},
        )
    ]
    mock_client = make_mock_client(list_tools_result=tools)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "ping", "--help"])
    assert result.exit_code == 0
    assert "none" in result.output.lower()


# --- C: コマンドヘルプ ---

def test_invoke_no_tool_name_shows_help():
    result = runner.invoke(app, ["invoke"])
    assert result.exit_code == 0
    assert "invoke" in result.output.lower()


# --- D: エラー系 ---

def test_invoke_invalid_json():
    mock_client = make_mock_client()
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search", "{not valid json}"])
    assert result.exit_code == 1
    assert "invalid JSON" in result.output


def test_invoke_non_object_json():
    mock_client = make_mock_client()
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search", "[1, 2, 3]"])
    assert result.exit_code == 1
    assert "JSON object" in result.output


def test_invoke_mcp_error():
    from navdoc.exceptions import MCPError

    mock_client = make_mock_client()
    mock_client.call_tool = AsyncMock(side_effect=MCPError("connection failed"))
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search"])
    assert result.exit_code == 1
    assert "connection failed" in result.output


def test_invoke_mcp_error_on_help(mock_tools):
    from navdoc.exceptions import MCPError

    mock_client = make_mock_client()
    mock_client.list_tools = AsyncMock(side_effect=MCPError("connection failed"))
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["invoke", "semantic_search", "--help"])
    assert result.exit_code == 1
    assert "connection failed" in result.output
