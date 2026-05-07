import os

from dotenv import load_dotenv

from .tools import NavdocTools
from .agent import NavdocAgent
from .models import AgentResponse

load_dotenv()

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

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        return await self._tools.search(query, top_k=top_k)

    async def get_document(self, url: str) -> dict:
        return await self._tools.get_document(url)

    async def ask(
        self,
        question: str,
        *,
        system_prompt: str = "",
        model: str = DEFAULT_MODEL,
        top_k: int = 5,
        temperature: float = 0.0,
        max_iterations: int = 10,
    ) -> AgentResponse:
        agent = NavdocAgent(anthropic_api_key=self._anthropic_api_key)
        mcp_tools = await self._tools.list_tools()

        async def call_tool(name: str, args: dict) -> dict:
            result = await self._tools._call_tool(name, args)
            parsed = self._tools._parse_tool_result(result)
            return parsed[0] if parsed else {}

        return await agent.ask(
            question,
            mcp_tools=mcp_tools,
            call_tool_fn=call_tool,
            system_prompt=system_prompt,
            model=model,
            top_k=top_k,
            temperature=temperature,
            max_iterations=max_iterations,
        )
