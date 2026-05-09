import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from navdoc.cli import app
from navdoc.models import StreamEvent

runner = CliRunner()


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


# --- chat command ---

def test_chat_initial_message_streams(tmp_path):
    config = write_config(tmp_path, {
        "name": "T", "description": "d", "system_prompt": "s",
        "user_prompt": "Hello",
        "placeholders": [],
    })
    events = [StreamEvent(type="text", delta="Hi there"), StreamEvent(type="done")]
    mock_client = make_streaming_client(events)
    with patch("navdoc.cli._make_client", return_value=mock_client):
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
    assert result.exit_code == 0
