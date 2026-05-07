import httpx
from mcp.client.streamable_http import streamable_http_client
from mcp.client.session import ClientSession
from mcp import types as mcp_types

from .exceptions import MCPError


class NavdocTools:
    """Low-level MCP tool wrappers. Each method opens a fresh connection (stateless)."""

    def __init__(self, api_key: str, account_id: str) -> None:
        self._api_key = api_key
        self._account_id = account_id
        self._mcp_url = f"https://mcp.navdoc.dev/{account_id}/mcp"

    def _make_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._api_key}"}
        )

    async def list_tools(self) -> list[mcp_types.Tool]:
        try:
            async with self._make_http_client() as http:
                async with streamable_http_client(self._mcp_url, http_client=http) as (r, w, _):
                    async with ClientSession(r, w) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        return result.tools
        except Exception as e:
            raise MCPError(f"Failed to list tools: {e}", original=e) from e

    async def _call_tool(self, name: str, arguments: dict) -> mcp_types.CallToolResult:
        try:
            async with self._make_http_client() as http:
                async with streamable_http_client(self._mcp_url, http_client=http) as (r, w, _):
                    async with ClientSession(r, w) as session:
                        await session.initialize()
                        return await session.call_tool(name, arguments)
        except MCPError:
            raise
        except Exception as e:
            raise MCPError(f"Tool call '{name}' failed: {e}", original=e) from e

    def _parse_tool_result(self, result: mcp_types.CallToolResult) -> list[dict]:
        if result.structuredContent:
            return [result.structuredContent]
        output = []
        for item in result.content:
            if hasattr(item, "text"):
                output.append({"text": item.text})
        return output
