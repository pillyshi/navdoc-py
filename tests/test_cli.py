import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types as mcp_types
from typer.testing import CliRunner

from navdoc.cli import app
from navdoc.models import StreamEvent

runner = CliRunner()


def make_mock_client(call_tool_result=None, list_tools_result=None):
    client = MagicMock()
    client.call_tool = AsyncMock(return_value=call_tool_result if call_tool_result is not None else [])
    client.list_tools = AsyncMock(return_value=list_tools_result if list_tools_result is not None else [])
    return client


def make_streaming_client(events: list[StreamEvent]):
    async def _stream(*args, **kwargs):
        for event in events:
            yield event

    client = MagicMock()
    client.stream = _stream
    return client


def write_config(tmp_path: Path, data: dict) -> Path:
    config = tmp_path / "config.json"
    config.write_text(json.dumps(data))
    return config


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


# --- ask command ---

def test_ask_streams_text(tmp_path):
    config = write_config(tmp_path, {
        "name": "Test",
        "description": "desc",
        "system_prompt": "be helpful",
        "user_prompt": "What is {{topic}}?",
        "placeholders": [{"key": "topic", "label": "Topic", "default": "asyncio"}],
    })
    events = [StreamEvent(type="text", delta="Hello "), StreamEvent(type="text", delta="world"), StreamEvent(type="done")]
    mock_client = make_streaming_client(events)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["ask", "--config", str(config)])
    assert result.exit_code == 0
    assert "Hello " in result.output
    assert "world" in result.output


def test_ask_missing_user_prompt(tmp_path):
    config = write_config(tmp_path, {"name": "T", "description": "d", "system_prompt": "s"})
    result = runner.invoke(app, ["ask", "--config", str(config)])
    assert result.exit_code == 1
    assert "user_prompt" in result.output


def test_ask_var_override(tmp_path):
    config = write_config(tmp_path, {
        "name": "T", "description": "d", "system_prompt": "s",
        "user_prompt": "Tell me about {{topic}}",
        "placeholders": [{"key": "topic", "label": "Topic", "default": "default"}],
    })
    captured = {}

    async def _stream(question, *, system_prompt="", **kwargs):
        captured["question"] = question
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.stream = _stream
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["ask", "--config", str(config), "--var", "topic=Python"])
    assert captured.get("question") == "Tell me about Python"


def test_ask_error_exits(tmp_path):
    from navdoc.exceptions import NavdocError

    config = write_config(tmp_path, {
        "name": "T", "description": "d", "system_prompt": "s",
        "user_prompt": "q",
    })

    async def _stream(*args, **kwargs):
        raise NavdocError("server down")
        yield  # make it a generator

    mock_client = MagicMock()
    mock_client.stream = _stream
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["ask", "--config", str(config)])
    assert result.exit_code == 1
    assert "server down" in result.output


# --- chat command (initial message only, no interactive loop) ---

def test_chat_initial_message_streams(tmp_path):
    config = write_config(tmp_path, {
        "name": "T", "description": "d", "system_prompt": "s",
        "user_prompt": "Hello",
        "placeholders": [],
    })
    events = [StreamEvent(type="text", delta="Hi there"), StreamEvent(type="done")]
    mock_client = make_streaming_client(events)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        # EOFError exits the interactive loop immediately after initial message
        result = runner.invoke(app, ["chat", "--config", str(config)], input="\x04")
    assert "Hi there" in result.output


def test_chat_no_initial_message_flag(tmp_path):
    config = write_config(tmp_path, {
        "name": "T", "description": "d", "system_prompt": "s",
        "user_prompt": "Hello",
    })
    mock_client = make_streaming_client([])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["chat", "--config", str(config), "--no-initial-message"], input="\x04")
    # stream() should not have been called
    assert result.exit_code == 0
