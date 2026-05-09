import os
from collections.abc import AsyncGenerator

from anthropic.types import MessageParam
from mcp import types as mcp_types

from .tools import NavdocTools
from .agent import NavdocAgent
from .models import AgentResponse, Document, Scope, StreamEvent, ToolCall
from .rest import NavdocREST
from .exceptions import NavdocError

DEFAULT_MODEL = "claude-sonnet-4-6"


class NavdocClient:
    """Entry point for the navdoc Python SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        account_id: str | None = None,
        anthropic_api_key: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("NAVDOC_API_KEY", "")
        self._account_id = account_id or os.environ.get("NAVDOC_ACCOUNT_ID", "")
        self._anthropic_api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")

        if not self._api_key:
            raise ValueError(
                "api_key is required. Pass api_key= or set NAVDOC_API_KEY env var."
            )
        if not self._account_id:
            raise ValueError(
                "account_id is required. Pass account_id= or set NAVDOC_ACCOUNT_ID env var."
            )

        self._tools = NavdocTools(self._api_key, self._account_id)
        self._rest = NavdocREST(self._api_key)

    async def list_tools(self) -> list[mcp_types.Tool]:
        return await self._tools.list_tools()

    async def call_tool(self, name: str, arguments: dict) -> list[dict]:
        result = await self._tools._call_tool(name, arguments)
        return self._tools._parse_tool_result(result)

    async def ask(
        self,
        question: str,
        *,
        messages: list[MessageParam] | None = None,
        system_prompt: str = "",
        model: str = DEFAULT_MODEL,
        tool_args: dict[str, dict] | None = None,
        temperature: float = 0.0,
        max_iterations: int = 10,
        tools: list[str] | None = None,
    ) -> AgentResponse:
        agent = NavdocAgent(anthropic_api_key=self._anthropic_api_key)
        mcp_tools = await self._tools.list_tools()

        if tools is not None:
            available_names = {t.name for t in mcp_tools}
            unknown = set(tools) - available_names
            if unknown:
                raise NavdocError(
                    f"Unknown tools: {sorted(unknown)}. Available: {sorted(available_names)}"
                )
            mcp_tools = [t for t in mcp_tools if t.name in set(tools)]

        async def call_tool(name: str, args: dict) -> dict:
            results = await self.call_tool(name, args)
            return results[0] if results else {}

        return await agent.ask(
            question,
            mcp_tools=mcp_tools,
            call_tool_fn=call_tool,
            prior_messages=messages,
            system_prompt=system_prompt,
            model=model,
            tool_args=tool_args,
            temperature=temperature,
            max_iterations=max_iterations,
        )

    async def list_documents(
        self,
        *,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        data = await self._rest.get(
            "/documents",
            params={"scope": scope, "limit": limit, "offset": offset},
        )
        items = data if isinstance(data, list) else data.get("items", data.get("documents", []))
        return [Document(document_id=d["document_id"], chunk_count=d["chunk_count"]) for d in items]

    async def upload_document(
        self,
        content: str,
        *,
        url: str,
        scope: str | None = None,
        created_at: str | None = None,
    ) -> Document:
        data = await self._rest.post(
            "/documents",
            body={"content": content, "url": url, "scope": scope, "created_at": created_at},
        )
        return Document(document_id=data["document_id"], chunk_count=data["chunk_count"])

    async def upload_chunks(
        self,
        chunks: list[str],
        *,
        document_url: str,
        scope: str | None = None,
    ) -> list[str]:
        data = await self._rest.post(
            "/documents/chunks",
            body={"chunks": chunks, "document_url": document_url, "scope": scope},
        )
        return data["chunk_ids"]

    async def delete_document(self, document_id: str) -> None:
        await self._rest.delete(f"/documents/{document_id}")

    async def list_scopes(self) -> list[Scope]:
        data = await self._rest.get("/scopes")
        items = data if isinstance(data, list) else []
        return [Scope(name=s["name"], visibility=s["visibility"]) for s in items]

    async def create_scope(self, name: str, *, visibility: str = "private") -> Scope:
        data = await self._rest.post("/scopes", body={"name": name, "visibility": visibility})
        return Scope(name=data["name"], visibility=data["visibility"])

    async def get_scope(self, name: str) -> Scope:
        data = await self._rest.get(f"/scopes/{name}")
        return Scope(name=data["name"], visibility=data["visibility"])

    async def update_scope(self, name: str, *, visibility: str) -> Scope:
        data = await self._rest.patch(f"/scopes/{name}", body={"visibility": visibility})
        return Scope(name=data["name"], visibility=data["visibility"])

    async def delete_scope(self, name: str) -> None:
        await self._rest.delete(f"/scopes/{name}")

    async def stream(
        self,
        question: str,
        *,
        messages: list[dict] | None = None,
        timezone: str | None = None,
        system_prompt: str = "",
    ) -> AsyncGenerator[StreamEvent, None]:
        all_messages = list(messages or []) + [{"role": "user", "content": question}]
        async for raw in self._rest.stream_post("/agent", body={
            "messages": all_messages,
            "timezone": timezone,
            "system_prompt": system_prompt or None,
        }):
            event = StreamEvent(
                type=raw["type"],
                delta=raw.get("delta"),
                name=raw.get("name"),
                input=raw.get("input"),
                message=raw.get("message"),
            )
            if event.type == "error":
                raise NavdocError(event.message or "Server error")
            yield event

    async def ask_server(
        self,
        question: str,
        *,
        messages: list[dict] | None = None,
        timezone: str | None = None,
        system_prompt: str = "",
    ) -> AgentResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        async for event in self.stream(
            question,
            messages=messages,
            timezone=timezone,
            system_prompt=system_prompt,
        ):
            if event.type == "text" and event.delta:
                text_parts.append(event.delta)
            elif event.type == "tool_result":
                tool_calls.append(ToolCall(
                    name=event.name or "",
                    input=event.input or {},
                    output={},
                ))
        return AgentResponse(
            answer="".join(text_parts),
            tool_calls=tool_calls,
            model="",
            usage={},
        )
