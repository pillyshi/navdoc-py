import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from navdoc.agent import NavdocAgent
from navdoc.models import AgentResponse
from navdoc.exceptions import MissingAnthropicKeyError, MaxIterationsError


def make_text_response(text: str, model: str = "claude-sonnet-4-6"):
    from anthropic.types import Message, TextBlock, Usage
    return Message(
        id="msg_end",
        model=model,
        role="assistant",
        type="message",
        stop_reason="end_turn",
        content=[TextBlock(text=text, type="text")],
        usage=Usage(input_tokens=100, output_tokens=50),
    )


def make_tool_use_response(tool_id: str, tool_name: str, tool_input: dict):
    from anthropic.types import Message, ToolUseBlock, Usage
    return Message(
        id="msg_tool",
        model="claude-sonnet-4-6",
        role="assistant",
        type="message",
        stop_reason="tool_use",
        content=[ToolUseBlock(id=tool_id, name=tool_name, input=tool_input, type="tool_use")],
        usage=Usage(input_tokens=80, output_tokens=30),
    )


def test_missing_key_raises():
    with pytest.raises(MissingAnthropicKeyError):
        NavdocAgent(anthropic_api_key=None)


def test_missing_key_env_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    agent = NavdocAgent()
    assert agent._client is not None


def make_mock_anthropic(side_effect=None, return_value=None):
    """Patch AsyncAnthropic constructor and return (patcher, mock_create)."""
    mock_messages = MagicMock()
    mock_create = AsyncMock(side_effect=side_effect, return_value=return_value)
    mock_messages.create = mock_create
    mock_client = MagicMock()
    mock_client.messages = mock_messages
    patcher = patch("navdoc.agent.AsyncAnthropic", return_value=mock_client)
    return patcher, mock_create


async def test_ask_no_tool_call(mock_mcp_tools):
    end_response = make_text_response("Direct answer")

    async def fake_call_tool(name, args):
        return {}

    patcher, _ = make_mock_anthropic(return_value=end_response)
    with patcher:
        agent = NavdocAgent(anthropic_api_key="sk-ant-test")
        response = await agent.ask(
            "What is asyncio?",
            mcp_tools=mock_mcp_tools,
            call_tool_fn=fake_call_tool,
        )

    assert isinstance(response, AgentResponse)
    assert response.answer == "Direct answer"
    assert response.tool_calls == []
    assert response.usage["input_tokens"] == 100
    assert response.usage["output_tokens"] == 50


async def test_ask_single_tool_call(mock_mcp_tools):
    tool_response = make_tool_use_response("tu_1", "search", {"query": "asyncio"})
    end_response = make_text_response("Answer after search")
    end_response.usage.input_tokens = 150
    end_response.usage.output_tokens = 60

    call_count = 0

    async def fake_call_tool(name, args):
        nonlocal call_count
        call_count += 1
        return {"text": '[{"title": "Result"}]'}

    patcher, _ = make_mock_anthropic(side_effect=[tool_response, end_response])
    with patcher:
        agent = NavdocAgent(anthropic_api_key="sk-ant-test")
        response = await agent.ask(
            "What is asyncio?",
            mcp_tools=mock_mcp_tools,
            call_tool_fn=fake_call_tool,
            tool_args={"search": {"top_k": 3}},
        )

    assert response.answer == "Answer after search"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "search"
    assert response.tool_calls[0].input["query"] == "asyncio"
    assert response.tool_calls[0].input["top_k"] == 3
    assert response.usage["input_tokens"] == 80 + 150
    assert response.usage["output_tokens"] == 30 + 60
    assert call_count == 1


async def test_ask_max_iterations_raises(mock_mcp_tools):
    tool_response = make_tool_use_response("tu_1", "search", {"query": "test"})

    async def fake_call_tool(name, args):
        return {"text": "result"}

    patcher, _ = make_mock_anthropic(return_value=tool_response)
    with patcher, pytest.raises(MaxIterationsError) as exc_info:
        agent = NavdocAgent(anthropic_api_key="sk-ant-test")
        await agent.ask(
            "loop forever",
            mcp_tools=mock_mcp_tools,
            call_tool_fn=fake_call_tool,
            max_iterations=2,
        )

    assert exc_info.value.iterations == 2


async def test_ask_with_system_prompt(mock_mcp_tools):
    end_response = make_text_response("Answer")

    patcher, mock_create = make_mock_anthropic(return_value=end_response)
    with patcher:
        agent = NavdocAgent(anthropic_api_key="sk-ant-test")
        await agent.ask(
            "question",
            mcp_tools=mock_mcp_tools,
            call_tool_fn=AsyncMock(return_value={}),
            system_prompt="You are a helpful assistant.",
        )

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs.get("system") == "You are a helpful assistant."
