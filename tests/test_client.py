import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from navdoc import NavdocClient
from navdoc.exceptions import MissingAnthropicKeyError
from navdoc.models import AgentResponse, ToolCall


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("NAVDOC_API_KEY", raising=False)
    monkeypatch.delenv("NAVDOC_ACCOUNT_ID", raising=False)
    with pytest.raises(ValueError, match="api_key"):
        NavdocClient(api_key="", account_id="acc")


def test_missing_account_id_raises(monkeypatch):
    monkeypatch.delenv("NAVDOC_ACCOUNT_ID", raising=False)
    with pytest.raises(ValueError, match="account_id"):
        NavdocClient(api_key="wf_test", account_id="")


def test_env_var_fallback(monkeypatch):
    monkeypatch.setenv("NAVDOC_API_KEY", "wf_env")
    monkeypatch.setenv("NAVDOC_ACCOUNT_ID", "acc_env")
    client = NavdocClient()
    assert client._api_key == "wf_env"
    assert client._account_id == "acc_env"


async def test_list_tools_returns_tools(mock_mcp_tools):
    with patch("navdoc.client.NavdocTools") as MockTools:
        mock_instance = MockTools.return_value
        mock_instance.list_tools = AsyncMock(return_value=mock_mcp_tools)

        client = NavdocClient(api_key="wf_test", account_id="acc_test")
        result = await client.list_tools()

    assert result == mock_mcp_tools


async def test_call_tool_returns_parsed_result():
    from unittest.mock import MagicMock
    raw = MagicMock()
    with patch("navdoc.client.NavdocTools") as MockTools:
        mock_instance = MockTools.return_value
        mock_instance._call_tool = AsyncMock(return_value=raw)
        mock_instance._parse_tool_result = MagicMock(return_value=[{"text": "result"}])

        client = NavdocClient(api_key="wf_test", account_id="acc_test")
        result = await client.call_tool("search", {"query": "test"})

    mock_instance._call_tool.assert_called_once_with("search", {"query": "test"})
    mock_instance._parse_tool_result.assert_called_once_with(raw)
    assert result == [{"text": "result"}]


async def test_ask_raises_missing_anthropic_key():
    with patch.dict("os.environ", {}, clear=True), pytest.raises(MissingAnthropicKeyError):
        client = NavdocClient(
            api_key="wf_test",
            account_id="acc_test",
            anthropic_api_key=None,
        )
        await client.ask("question")


async def test_ask_returns_agent_response(mock_mcp_tools):
    expected = AgentResponse(
        answer="answer",
        tool_calls=[],
        model="claude-sonnet-4-6",
        usage={"input_tokens": 10, "output_tokens": 5},
    )

    with patch("navdoc.client.NavdocTools") as MockTools, \
         patch("navdoc.client.NavdocAgent") as MockAgent:
        mock_tools = MockTools.return_value
        mock_tools.list_tools = AsyncMock(return_value=mock_mcp_tools)
        mock_tools._call_tool = AsyncMock()
        mock_tools._parse_tool_result = MagicMock(return_value=[{}])

        mock_agent = MockAgent.return_value
        mock_agent.ask = AsyncMock(return_value=expected)

        client = NavdocClient(
            api_key="wf_test",
            account_id="acc_test",
            anthropic_api_key="sk-ant-test",
        )
        result = await client.ask("What is asyncio?", top_k=5)

    assert result is expected
    mock_agent.ask.assert_called_once()
    call_kwargs = mock_agent.ask.call_args.kwargs
    assert call_kwargs["top_k"] == 5
