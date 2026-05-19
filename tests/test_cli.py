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

def test_ask_direct_question():
    events = [StreamEvent(type="text", delta="Hello"), StreamEvent(type="done")]
    mock_client = make_streaming_client(events)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["ask", "What is asyncio?"])
    assert result.exit_code == 0
    assert "Hello" in result.output


def test_ask_direct_question_with_system_prompt():
    captured = {}

    async def _stream(question, *, system_prompt="", **kwargs):
        captured["system_prompt"] = system_prompt
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.stream = _stream
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["ask", "Hello", "--system-prompt", "Be concise."])
    assert captured.get("system_prompt") == "Be concise."


def test_ask_no_args_errors():
    result = runner.invoke(app, ["ask"])
    assert result.exit_code == 1


def test_ask_question_and_config_errors(tmp_path):
    config = write_config(tmp_path, {"name": "T", "description": "d", "system_prompt": "s", "user_prompt": "q"})
    result = runner.invoke(app, ["ask", "hello", "--config", str(config)])
    assert result.exit_code == 1


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


def test_chat_without_config():
    mock_client = make_streaming_client([])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["chat"], input="\x04")
    assert result.exit_code == 0


def test_chat_without_config_with_system_prompt():
    mock_client = make_streaming_client([])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["chat", "--system-prompt", "Be concise."], input="\x04")
    assert result.exit_code == 0


# --- --template option ---

def make_template_client(template, events: list[StreamEvent]):
    from navdoc.models import AgentTemplate

    async def _get_template(template_id: str):
        return template

    async def _stream(*args, **kwargs):
        for event in events:
            yield event

    client = MagicMock()
    client.get_template = _get_template
    client.stream = _stream
    return client


def make_agent_template(
    template_id="aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb",
    name="Test Template",
    system_prompt="Be helpful.",
    user_prompt="Tell me about {{topic}}",
    placeholders=None,
    greeting=None,
):
    from navdoc.models import AgentTemplate, TemplatePlaceholder

    if placeholders is None:
        placeholders = [TemplatePlaceholder(key="topic", label="Topic", default="Python")]
    return AgentTemplate(
        id=template_id,
        name=name,
        description=None,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        placeholders=placeholders,
        tools=None,
        greeting=greeting,
        required_scope_description=None,
        is_public=False,
        star_count=0,
        is_starred=False,
        is_mine=True,
    )


def test_ask_template_fetches_and_streams():
    template = make_agent_template()
    captured = {}

    async def _get_template(template_id):
        return template

    async def _stream(*args, **kwargs):
        captured["template_id"] = kwargs.get("template_id")
        captured["question"] = args[0] if args else kwargs.get("question")
        yield StreamEvent(type="text", delta="Answer")
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.get_template = _get_template
    mock_client.stream = _stream

    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["ask", "--template", template.id])

    assert result.exit_code == 0
    assert "Answer" in result.output
    assert captured["template_id"] == template.id
    assert "Python" in captured["question"]


def test_ask_template_var_override():
    template = make_agent_template()
    captured = {}

    async def _get_template(template_id):
        return template

    async def _stream(*args, **kwargs):
        captured["question"] = args[0] if args else kwargs.get("question")
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.get_template = _get_template
    mock_client.stream = _stream

    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["ask", "--template", template.id, "--var", "topic=Rust"])

    assert captured.get("question") == "Tell me about Rust"


def test_ask_template_auto_placeholder_skipped():
    from navdoc.models import AgentTemplate, TemplatePlaceholder

    template = make_agent_template(
        user_prompt="Hello world",
        placeholders=[TemplatePlaceholder(key="ctx", label="Context", auto=True)],
    )
    prompted = []

    async def _get_template(template_id):
        return template

    async def _stream(*args, **kwargs):
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.get_template = _get_template
    mock_client.stream = _stream

    with patch("navdoc.cli._make_client", return_value=mock_client):
        with patch("navdoc.cli.Prompt.ask", side_effect=lambda label: prompted.append(label) or ""):
            result = runner.invoke(app, ["ask", "--template", template.id])

    assert result.exit_code == 0
    assert "ctx" not in [p for p in prompted]


def test_ask_template_and_config_mutually_exclusive(tmp_path):
    config = write_config(tmp_path, {"name": "T", "description": "d", "system_prompt": "s", "user_prompt": "q"})
    result = runner.invoke(app, ["ask", "--config", str(config), "--template", "some-uuid"])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


def test_ask_template_and_question_mutually_exclusive():
    result = runner.invoke(app, ["ask", "hello", "--template", "some-uuid"])
    assert result.exit_code == 1


def test_ask_template_missing_user_prompt():
    from navdoc.models import AgentTemplate

    template = make_agent_template(user_prompt=None)

    async def _get_template(template_id):
        return template

    mock_client = MagicMock()
    mock_client.get_template = _get_template

    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["ask", "--template", template.id])

    assert result.exit_code == 1
    assert "user_prompt" in result.output


def test_ask_template_api_error():
    from navdoc.exceptions import NavdocError

    async def _get_template(template_id):
        raise NavdocError("not found")

    mock_client = MagicMock()
    mock_client.get_template = _get_template

    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["ask", "--template", "bad-uuid"])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_chat_template_sets_template_id():
    template = make_agent_template(user_prompt="Hello")
    captured = {}

    async def _get_template(template_id):
        return template

    async def _stream(*args, **kwargs):
        captured["template_id"] = kwargs.get("template_id")
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.get_template = _get_template
    mock_client.stream = _stream

    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["chat", "--template", template.id], input="\x04")

    assert result.exit_code == 0
    assert captured.get("template_id") == template.id


def test_chat_template_greeting_displayed():
    template = make_agent_template(user_prompt=None, greeting="Hello! How can I help?")
    captured = {}

    async def _get_template(template_id):
        return template

    async def _stream(*args, **kwargs):
        captured["called"] = True
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.get_template = _get_template
    mock_client.stream = _stream

    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["chat", "--template", template.id], input="\x04")

    assert result.exit_code == 0
    assert "Hello! How can I help?" in result.output
    assert not captured.get("called")  # no API call since no user_prompt


def test_chat_template_and_config_mutually_exclusive(tmp_path):
    config = write_config(tmp_path, {"name": "T", "description": "d", "system_prompt": "s"})
    result = runner.invoke(app, ["chat", "--config", str(config), "--template", "some-uuid"])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


def test_ask_config_tools_passed_to_stream(tmp_path):
    config = write_config(tmp_path, {
        "name": "T", "description": "d",
        "system_prompt": "s",
        "user_prompt": "Tell me about {{topic}}",
        "tools": ["search_by_url", "add_document"],
        "placeholders": [{"key": "topic", "label": "Topic", "default": "Python"}],
    })
    captured = {}

    async def _stream(question, *, tools=None, **kwargs):
        captured["tools"] = tools
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.stream = _stream
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["ask", "--config", str(config)])
    assert captured.get("tools") == ["search_by_url", "add_document"]


def test_chat_config_tools_passed_to_stream(tmp_path):
    config = write_config(tmp_path, {
        "name": "T", "description": "d",
        "system_prompt": "s",
        "user_prompt": "Hello",
        "tools": ["semantic_search"],
        "placeholders": [],
    })
    captured = {}
    call_count = 0

    async def _stream(question, *, tools=None, **kwargs):
        nonlocal call_count
        call_count += 1
        captured["tools"] = tools
        yield StreamEvent(type="text", delta="Hi")
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.stream = _stream
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["chat", "--config", str(config)], input="exit\n")
    assert captured.get("tools") == ["semantic_search"]


def test_chat_hides_pre_tool_text(tmp_path):
    """Text before a tool call is discarded; only post-tool text is shown."""
    config = write_config(tmp_path, {
        "name": "T", "description": "d", "system_prompt": "s",
        "user_prompt": "Hello", "placeholders": [],
    })

    async def _stream(*args, **kwargs):
        yield StreamEvent(type="text", delta="I'll search for that.")
        yield StreamEvent(type="tool_use", name="semantic_search")
        yield StreamEvent(type="tool_result")
        yield StreamEvent(type="text", delta="Here is the answer.")
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.stream = _stream
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["chat", "--config", str(config)], input="exit\n")

    assert "Here is the answer." in result.output
    assert "I'll search for that." not in result.output


def test_chat_hides_between_tool_text(tmp_path):
    """Text between multiple tool calls is also discarded."""
    config = write_config(tmp_path, {
        "name": "T", "description": "d", "system_prompt": "s",
        "user_prompt": "Hello", "placeholders": [],
    })

    async def _stream(*args, **kwargs):
        yield StreamEvent(type="text", delta="Let me check the date.")
        yield StreamEvent(type="tool_use", name="get_date")
        yield StreamEvent(type="tool_result")
        yield StreamEvent(type="text", delta="Now let me search the log.")
        yield StreamEvent(type="tool_use", name="semantic_search")
        yield StreamEvent(type="tool_result")
        yield StreamEvent(type="text", delta="Final answer.")
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.stream = _stream
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["chat", "--config", str(config)], input="exit\n")

    assert "Final answer." in result.output
    assert "Let me check the date." not in result.output
    assert "Now let me search the log." not in result.output


def test_chat_shows_text_without_tool_call(tmp_path):
    """When no tool calls occur, the full text is shown."""
    config = write_config(tmp_path, {
        "name": "T", "description": "d", "system_prompt": "s",
        "user_prompt": "Hello", "placeholders": [],
    })

    async def _stream(*args, **kwargs):
        yield StreamEvent(type="text", delta="Direct answer.")
        yield StreamEvent(type="done")

    mock_client = MagicMock()
    mock_client.stream = _stream
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["chat", "--config", str(config)], input="exit\n")

    assert "Direct answer." in result.output
