import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from navdoc import NavdocClient, StreamEvent
from navdoc.models import AgentResponse, ToolCall
from navdoc.exceptions import NavdocError
from navdoc.rest import NavdocREST


@pytest.fixture
def client():
    with patch("navdoc.client.NavdocREST"):
        return NavdocClient(api_key="wf_test")


def make_sse_lines(*events: dict) -> list[str]:
    return [f"data: {json.dumps(e)}" for e in events]


async def async_lines(lines: list[str]):
    for line in lines:
        yield line


# --- stream() tests ---

async def test_stream_yields_text_events(client):
    lines = make_sse_lines(
        {"type": "text", "delta": "Hello "},
        {"type": "text", "delta": "world"},
        {"type": "done"},
    )

    async def mock_stream_post(path, body):
        for line in lines:
            yield json.loads(line[6:])

    client._rest.stream_post = mock_stream_post

    events = [e async for e in client.stream("Hi")]
    assert events == [
        StreamEvent(type="text", delta="Hello "),
        StreamEvent(type="text", delta="world"),
        StreamEvent(type="done"),
    ]


async def test_stream_yields_tool_events(client):
    lines = make_sse_lines(
        {"type": "tool_use", "name": "search", "input": {"query": "x"}},
        {"type": "tool_result", "name": "search", "input": {"query": "x"}},
        {"type": "done"},
    )

    async def mock_stream_post(path, body):
        for line in lines:
            yield json.loads(line[6:])

    client._rest.stream_post = mock_stream_post

    events = [e async for e in client.stream("q")]
    assert events[0] == StreamEvent(type="tool_use", name="search", input={"query": "x"})
    assert events[1] == StreamEvent(type="tool_result", name="search", input={"query": "x"})


async def test_stream_raises_on_error_event(client):
    async def mock_stream_post(path, body):
        yield {"type": "error", "message": "something broke"}

    client._rest.stream_post = mock_stream_post

    with pytest.raises(NavdocError, match="something broke"):
        async for _ in client.stream("q"):
            pass


async def test_stream_sends_correct_body(client):
    received = {}

    async def mock_stream_post(path, body):
        received["path"] = path
        received["body"] = body
        yield {"type": "done"}

    client._rest.stream_post = mock_stream_post

    async for _ in client.stream(
        "question",
        messages=[{"role": "user", "content": "prev"}],
        timezone="Asia/Tokyo",
        system_prompt="be helpful",
    ):
        pass

    assert received["path"] == "/agent"
    assert received["body"]["messages"] == [
        {"role": "user", "content": "prev"},
        {"role": "user", "content": "question"},
    ]
    assert received["body"]["timezone"] == "Asia/Tokyo"
    assert received["body"]["template"]["system_prompt"] == "be helpful"
    assert "tools" not in received["body"].get("template", {})


async def test_stream_sends_tools_in_template(client):
    received = {}

    async def mock_stream_post(path, body):
        received["body"] = body
        yield {"type": "done"}

    client._rest.stream_post = mock_stream_post

    async for _ in client.stream(
        "question",
        system_prompt="be helpful",
        tools=["search_by_url", "add_document"],
    ):
        pass

    assert received["body"]["template"]["system_prompt"] == "be helpful"
    assert received["body"]["template"]["tools"] == ["search_by_url", "add_document"]
    assert "template_id" in received["body"]


async def test_stream_template_id_omits_template_object(client):
    received = {}

    async def mock_stream_post(path, body):
        received["body"] = body
        yield {"type": "done"}

    client._rest.stream_post = mock_stream_post

    async for _ in client.stream(
        "question",
        template_id="aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb",
        system_prompt="ignored",
        tools=["search_by_url"],
    ):
        pass

    assert received["body"]["template_id"] == "aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb"
    assert "template" not in received["body"]


async def test_stream_sends_user_prompt_in_template(client):
    received = {}

    async def mock_stream_post(path, body):
        received["body"] = body
        yield {"type": "done"}

    client._rest.stream_post = mock_stream_post

    async for _ in client.stream("q", user_prompt="Tell me about {{topic}}"):
        pass

    assert received["body"]["template"]["user_prompt"] == "Tell me about {{topic}}"


async def test_stream_sends_temperature_in_template(client):
    received = {}

    async def mock_stream_post(path, body):
        received["body"] = body
        yield {"type": "done"}

    client._rest.stream_post = mock_stream_post

    async for _ in client.stream("q", temperature=0.5):
        pass

    assert received["body"]["template"]["temperature"] == 0.5


# --- ask_server() tests ---

async def test_ask_server_returns_response(client):
    client._rest.post = AsyncMock(return_value={"response": "The answer is 42"})
    result = await client.ask_server("What is the answer?")
    assert isinstance(result, AgentResponse)
    assert result.answer == "The answer is 42"
    assert result.tool_calls == []


async def test_ask_server_sends_correct_body(client):
    client._rest.post = AsyncMock(return_value={"response": ""})
    await client.ask_server("q", system_prompt="be helpful", tools=["search"])
    call_body = client._rest.post.call_args[1]["body"]
    assert call_body["message"] == "q"
    assert call_body["template"]["system_prompt"] == "be helpful"
    assert "output_format" not in call_body  # output_format is inside template, not top-level


async def test_ask_server_output_format_in_template(client):
    client._rest.post = AsyncMock(return_value={"response": None})
    await client.ask_server("q", output_format="none")
    call_body = client._rest.post.call_args[1]["body"]
    assert call_body["template"]["output_format"] == "none"
    assert "output_format" not in call_body


async def test_ask_server_raises_on_error(client):
    client._rest.post = AsyncMock(side_effect=NavdocError("internal error"))
    with pytest.raises(NavdocError):
        await client.ask_server("q")


# --- NavdocREST.stream_post() tests ---

async def test_rest_stream_post_parses_sse():
    rest = NavdocREST("wf_test")

    async def fake_aiter_lines():
        for line in [
            'data: {"type": "text", "delta": "hi"}',
            "",
            'data: {"type": "done"}',
        ]:
            yield line

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = fake_aiter_lines

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_ctx
        )
        events = [e async for e in rest.stream_post("/agent", body={"messages": []})]

    assert events == [{"type": "text", "delta": "hi"}, {"type": "done"}]


async def test_rest_stream_post_raises_auth_error():
    rest = NavdocREST("wf_bad")

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    from navdoc.exceptions import AuthError

    with patch("navdoc.rest.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_ctx
        )
        with pytest.raises(AuthError):
            async for _ in rest.stream_post("/agent", body={"messages": []}):
                pass
