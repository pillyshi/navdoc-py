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
    assert received["body"]["system_prompt"] == "be helpful"


# --- ask_server() tests ---

async def test_ask_server_collects_answer(client):
    async def mock_stream_post(path, body):
        for event in [
            {"type": "text", "delta": "The answer is "},
            {"type": "text", "delta": "42"},
            {"type": "done"},
        ]:
            yield event

    client._rest.stream_post = mock_stream_post

    result = await client.ask_server("What is the answer?")
    assert isinstance(result, AgentResponse)
    assert result.answer == "The answer is 42"
    assert result.tool_calls == []


async def test_ask_server_collects_tool_calls(client):
    async def mock_stream_post(path, body):
        for event in [
            {"type": "tool_use", "name": "search", "input": {"query": "x"}},
            {"type": "tool_result", "name": "search", "input": {"query": "x"}},
            {"type": "text", "delta": "Found it"},
            {"type": "done"},
        ]:
            yield event

    client._rest.stream_post = mock_stream_post

    result = await client.ask_server("Find x")
    assert result.answer == "Found it"
    assert result.tool_calls == [ToolCall(name="search", input={"query": "x"}, output={})]


async def test_ask_server_raises_on_error(client):
    async def mock_stream_post(path, body):
        yield {"type": "error", "message": "internal error"}

    client._rest.stream_post = mock_stream_post

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
