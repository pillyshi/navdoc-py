import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mcp import types as mcp_types

from navdoc.tools import NavdocTools
from navdoc.exceptions import MCPError


def make_session_mock(list_tools_result=None, call_tool_result=None):
    session = AsyncMock()
    session.initialize = AsyncMock()
    if list_tools_result is not None:
        session.list_tools = AsyncMock(return_value=list_tools_result)
    if call_tool_result is not None:
        session.call_tool = AsyncMock(return_value=call_tool_result)
    return session


def patch_mcp(session_mock):
    """Return a context manager that patches streamable_http_client and ClientSession."""
    http_cm = MagicMock()
    http_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    http_cm.__aexit__ = AsyncMock(return_value=None)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session_mock)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    p1 = patch("navdoc.tools.streamable_http_client", return_value=http_cm)
    p2 = patch("navdoc.tools.ClientSession", return_value=session_cm)
    return p1, p2


async def test_list_tools_returns_tool_list(mock_mcp_tools):
    list_result = MagicMock()
    list_result.tools = mock_mcp_tools
    session = make_session_mock(list_tools_result=list_result)
    p1, p2 = patch_mcp(session)

    with p1, p2:
        tools = NavdocTools("wf_test", "acc_test")
        result = await tools.list_tools()

    assert result == mock_mcp_tools


async def test_call_tool_wraps_exception_as_mcp_error():
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.call_tool = AsyncMock(side_effect=RuntimeError("connection refused"))
    p1, p2 = patch_mcp(session)

    with p1, p2, pytest.raises(MCPError) as exc_info:
        tools = NavdocTools("wf_test", "acc_test")
        await tools._call_tool("search", {})

    assert isinstance(exc_info.value.original, RuntimeError)


def test_parse_tool_result_with_structured_content():
    tools = NavdocTools("wf_test", "acc_test")
    result = MagicMock()
    result.structuredContent = {"key": "value"}
    result.content = []

    parsed = tools._parse_tool_result(result)
    assert parsed == [{"key": "value"}]


def test_parse_tool_result_falls_back_to_text_content():
    tools = NavdocTools("wf_test", "acc_test")
    result = mcp_types.CallToolResult(
        content=[mcp_types.TextContent(type="text", text="hello")]
    )

    parsed = tools._parse_tool_result(result)
    assert parsed == [{"text": "hello"}]
