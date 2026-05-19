import os
from collections.abc import AsyncGenerator

from .models import AgentResponse, AgentTemplate, Document, Scope, StreamEvent, TemplatePlaceholder, ToolCall
from .rest import NavdocREST
from .exceptions import NavdocError


class NavdocClient:
    """Entry point for the navdoc Python SDK."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("NAVDOC_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "api_key is required. Pass api_key= or set NAVDOC_API_KEY env var."
            )
        self._rest = NavdocREST(self._api_key)

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
        template_id: str | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        all_messages = list(messages or []) + [{"role": "user", "content": question}]
        async for raw in self._rest.stream_post("/agent", body={
            "messages": all_messages,
            "timezone": timezone,
            "system_prompt": system_prompt or None,
            "template_id": template_id,
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
        template_id: str | None = None,
    ) -> AgentResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        async for event in self.stream(
            question,
            messages=messages,
            timezone=timezone,
            system_prompt=system_prompt,
            template_id=template_id,
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

    @staticmethod
    def _parse_template(data: dict) -> AgentTemplate:
        placeholders = [
            TemplatePlaceholder(
                key=p["key"],
                label=p["label"],
                auto=p.get("auto", False),
                default=p.get("default"),
            )
            for p in data.get("placeholders") or []
        ]
        return AgentTemplate(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            system_prompt=data.get("system_prompt"),
            user_prompt=data.get("user_prompt"),
            placeholders=placeholders,
            tools=data.get("tools"),
            greeting=data.get("greeting"),
            required_scope_description=data.get("required_scope_description"),
            is_public=data.get("is_public", False),
            star_count=data.get("star_count", 0),
            is_starred=data.get("is_starred", False),
            is_mine=data.get("is_mine", False),
        )

    async def list_templates(self) -> list[AgentTemplate]:
        data = await self._rest.get("/agent-templates")
        items = data if isinstance(data, list) else data.get("items", [])
        return [self._parse_template(t) for t in items]

    async def get_template(self, template_id: str) -> AgentTemplate:
        templates = await self.list_templates()
        for t in templates:
            if t.id == template_id:
                return t
        raise NavdocError(f"Template '{template_id}' not found")

    async def create_template(self, payload: dict) -> AgentTemplate:
        data = await self._rest.post("/agent-templates", body=payload)
        return self._parse_template(data)

    async def update_template(self, template_id: str, payload: dict) -> AgentTemplate:
        data = await self._rest.patch(f"/agent-templates/{template_id}", body=payload)
        return self._parse_template(data)

    async def delete_template(self, template_id: str) -> None:
        await self._rest.delete(f"/agent-templates/{template_id}")
